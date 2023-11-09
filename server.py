import socket
import threading
import time
import json
import binascii
import select
import random
from queue import Queue

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
port = 0
fila = Queue()
retransmissionQueue = Queue()
is_token_holder = False
token_time = 0
token = "9000"

is_message_confirmed = False  # variavel de controle de confirmação de retorno da mensagem
timeout_limit = 50 # timer para a confirmação de retorno da mensagem

max_token_pass_time = 10  # tempo máximo para o token passar pela rede
min_token_pass_time = 1   # tempo mínimo para o token passar pela rede

# Estrutura do pacote de dados
class DataPacket:
    def __init__(self, control_error, source, destination, crc, message):
        self.control_error = control_error
        self.source = source
        self.destination = destination
        self.crc = crc
        self.message = message

    def to_string(self):
        return f"7777:{self.control_error};{self.source};{self.destination};{self.crc};{self.message}"
    
def timeTokenControl():
    pass

# Transmissao do Token
def passesToken():
    global is_token_holder
    is_token_holder = False
    client_socket.sendto(token.encode(), (destination, port))
    print("Transmissao do Token")

# tempo que elas permanecerão com os pacotes (para fins de depuração)
def debugging():
    time.sleep(token_time)

def crc32(msg):
    # Calcula o valor CRC32 para a mensagem
    crc_value = binascii.crc32(msg.encode('utf-8'))
    return crc_value

def insertFailure(dst, message):
    # Aqui, você pode adotar diferentes estratégias para introduzir erros
    # Por exemplo, inverter um caractere na mensagem
    index = random.randint(0, len(message) - 1)
    modified_message = message[:index] + chr((ord(message[index]) + 1) % 256) + message[index+1:]
    print(f"Mensagem com falha adicionada: {modified_message}")
    return modified_message


def process_message(packet):
    packet = packet.split(";")

    err = packet[0].split(":")[1]
    src = packet[1]
    dst = packet[2]
    crc = int(packet[3])
    msg = packet[4]

    newCRC = crc32(msg)

    if dst != "TODOS":
        if crc == newCRC:
            err = "ACK"
        else:
            err = "NACK"

    print(f"{src} : {msg}")

    packet = DataPacket(err, src, dst, crc, msg)
    packet_str = packet.to_string()
    return packet_str

# Implementação do servidor para receber e processar mensagens.
def receive_message(destination, machine_name):
    global is_token_holder, is_message_confirmed

    #receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(("0.0.0.0", port))

    while True:
            # Recebendo pacotes
            data, addr = client_socket.recvfrom(1024) #tranca aqui
            received_packet = data.decode('utf-8')

            # tempo que elas permanecerão com os pacotes (para fins de depuração), em segundos
            debugging()

            # Lógica para manipular os pacotes recebidos
            # verifica se é o token
            if received_packet.startswith(token):
                if fila.empty():
                    #repassa token
                    passesToken()
                else:
                    is_token_holder = True
                    print("Token recebido")
            
            if received_packet.startswith("7777"):
                packet = received_packet.split(";")

                # Campo origem, caso o pacote de dados seja recebido por quem o originou 
                if packet[1] == machine_name:
                    packet = packet[0].split(":")

                    if packet[1] == "naoexiste":
                        print("máquina destino não se encontra na rede ou está desligada")
                        fila.get()
                        passesToken()

                    if packet[1] == "NACK":
                        retransmissionQueue.put(fila.queue[0])  # Adiciona o elemento da fila principal na fila de retransmissão
                        passesToken()

                    if packet[1] == "ACK":
                        print("o pacote foi recebido corretamente pela máquina destino")
                        fila.get()
                        passesToken()

                    is_message_confirmed = True

                # Campo destino, a estação identifica se o mesmo é endereçado a ela
                elif packet[2] == machine_name:
                    received_packet = process_message(received_packet)
                    client_socket.sendto(received_packet.encode('utf-8'), (destination, port))

                elif packet[2] == "TODOS":
                    # Broadcast -> manter o pacote em “naoexiste” (ninguem confirma)
                    received_packet = process_message(received_packet)
                    client_socket.sendto(received_packet.encode('utf-8'), (destination, port))

                #repassa pacote
                else:
                    client_socket.sendto(received_packet.encode('utf-8'), (destination, port))


# Função para enviar mensagens
def send_message(destination, machine_name):
    global is_message_confirmed
    while True:
        if is_token_holder and not fila.empty():
            # Código para enviar mensagens
            dst_data = fila.queue[0].split(":")

            dst = dst_data[0].replace(" ", "")    # pega o apelido da maquina destino
            msg = dst_data[1].replace(" ", "", 1) # pega a mensagem
            crc = 0

            # Garantia da espefificação que diz:
            # Caso o pacote venha com NACK, o mesmo deve ser retransmitido apenas uma vez na rede, trocando o NACK por naoexiste, 
            # colocando a mensagem original sem erro e enviando a mensagem para a máquina a sua direita na próxima passagem do token.
            if not transmissionQueue.empty() and transmissionQueue.queue[0] == fila.queue[0]:
                msg = msg.replace("-f", "") # remove o -f de falha
            
            #  módulo de inserção de falhas
            # A aplicação deve implementar um módulo de inserção de falhas que force as máquinas a inserir erros aleatoriamente nas mensagens.
            # Escolha foi Forçar manualmente a falha
            if "-f" in msg:
                msg = msg.replace("-f", "") # remove o -f de falha
                crc = crc32(msg) # cacula a mensagem sem falha (induzir ao erro no destino)
                msg = insertFailure(dst, msg) # adiciona falha
            else:
                crc = crc32(msg) # calcula a mensagem sem falha (normal)


            # monta pacote
            data_packet = DataPacket("naoexiste", machine_name, dst, crc, msg)
            packet_string = data_packet.to_string()

            # envia pacote
            client_socket.sendto(packet_string.encode('utf-8'), (destination, port))

            # Aguarda a confirmação de retorno da mensagem
            start_time = time.time()
            while not is_message_confirmed:
                if time.time() - start_time > timeout_limit:
                    # Se o tempo limite foi atingido, sai do loop de espera
                    print("Timeout atingido. Mensagem não confirmada.")
                    fila.get()
                    passesToken()
                    break
                pass  # Espera pela confirmação

            # Reset da variável para a próxima mensagem.
            is_message_confirmed = False 

# Leitura do arquivo de configuração GPT então tem que ver
def read_config_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        destination = lines[0].strip().split(":")
        dest = destination[0]
        port = int(destination[1])
        machine_name = lines[1].strip()
        token_time = int(lines[2].strip())
        is_token_holder = lines[3].strip() == 'true'
        return dest, port, machine_name, token_time, is_token_holder

if __name__ == '__main__':

    # Carregando configurações do arquivo
    destination, port, machine_name, token_time, is_token_holder = read_config_file('config.txt')

    # Iniciando para enviar menssagens
    send_message_thread = threading.Thread(target=send_message, args=(destination, machine_name))
    send_message_thread.start()

    # Iniciando para receber menssagens
    receive_message_thread = threading.Thread(target=receive_message, args=(destination, machine_name))
    receive_message_thread.start()

    # if is_token_holder:
    #     timeTokenControl_thread = threading.Thread(target=timeTokenControl())
    #     timeTokenControl_thread.start()

    # Lógica para envio de mensagens
    while True:
        # Recebendo a entrada do usuário
        elemento = input() # exemplo "bob : Oiiii" -> "# (destino) (mensagem)"

        if fila.qsize() == 10:
            print("Fila de mensagens cheia")
        else:
            # Adicionando o elemento à fila
            fila.put(elemento)

