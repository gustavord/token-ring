import socket
import threading
import time
import json
import binascii
import select
import random
from queue import Queue

# Códigos ANSI para cores no terminal
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
port = 0
fila = Queue()
retransmissionQueue = Queue()
is_token_holder = False
token_time = 0
token = "9000"

is_message_confirmed = False  # variavel de controle de confirmação de retorno da mensagem
timeout_limit = 15 # timer para a confirmação de retorno da mensagem

#error_probability = 0.2  # Probabilidade de erro, por exemplo 20%

# Constantes para controle de tempo
TIMEOUT_THRESHOLD = 20  # Tempo limite para detectar timeout do token
MIN_TOKEN_PASS_TIME = 5  # Tempo mínimo para passagem do token entre as estações

# Variáveis para controle do token
token_last_passed = time.time()

# Variavel para remover Token
withdrawToken = False

# Função para controlar o tempo do token
def timeTokenControl():
    global token_last_passed, is_token_holder

    while True:
        if is_token_holder:
            token_holder_time = time.time() - token_last_passed
            if token_holder_time > TIMEOUT_THRESHOLD:
                # Caso que fica com o token e não faz nada
                print(f"{bcolors.WARNING}Transmitindo token por inatividade{bcolors.WARNING}")
                passesToken()
            
        # Veifica quanto tempo o token nao eh recebido (token = false)
        if not is_token_holder:        
            token_passed_time = time.time() - token_last_passed
            if token_passed_time > TIMEOUT_THRESHOLD:
                # Caso o token não passe dentro do tempo limite (timeout), gera um novo token
                print(f"{bcolors.WARNING}Timeout detectado. Gerando Token{bcolors.WARNING}")
                is_token_holder = True
                token_last_passed = time.time()

        time.sleep(1)

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

# Transmissao do Token
def passesToken():
    global is_token_holder, token_last_passed
    is_token_holder = False
    client_socket.sendto(token.encode(), (destination, port))
    token_last_passed = time.time()
    print(f"{bcolors.OKBLUE}Transmissao do Token{bcolors.OKBLUE}")

# tempo que elas permanecerão com os pacotes (para fins de depuração)
def debugging():
    print(f"{bcolors.OKBLUE}Processando mensagem{bcolors.OKBLUE}")
    time.sleep(token_time)

def crc32(msg):
    # Calcula o valor CRC32 para a mensagem
    crc_value = binascii.crc32(msg.encode('utf-8'))
    return crc_value

def insertFailure(dst, message):
    # estamos inserindo a falha de forma manual e controlada, para automatiza bastaria descomentar o if e o return
    # Verifica se um erro deve ser introduzido com base na probabilidade
    #if random.random() < error_probability:

    # Aqui, você pode adotar diferentes estratégias para introduzir erros
    # Por exemplo, inverter um caractere na mensagem
    index = random.randint(0, len(message) - 1)
    modified_message = message[:index] + chr((ord(message[index]) + 1) % 256) + message[index+1:]
    print(f"{bcolors.FAIL}Mensagem com falha adicionada: {modified_message}{bcolors.FAIL}")
    return modified_message
    
    # Se nenhum erro for introduzido, retorna a mensagem original
    #return message


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

    print(f"{bcolors.OKGREEN}{src} <==> {msg}{bcolors.OKGREEN}")

    packet = DataPacket(err, src, dst, crc, msg)
    packet_str = packet.to_string()
    return packet_str

# Implementação do servidor para receber e processar mensagens.
def receive_message(destination, machine_name):
    global is_token_holder, is_message_confirmed, token_last_passed, withdrawToken

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
                    # Controla o tempo mínimo de passagem do token
                    token_holder_time = time.time() - token_last_passed
                    if token_holder_time < MIN_TOKEN_PASS_TIME:
                        # Caso o token passe em um tempo menor que o mínimo, retina este token
                        print(f"{bcolors.WARNING}Detectada passagem de mais de um token na rede. Retirando token.{bcolors.WARNING}")
                        is_token_holder = False
                    else:
                        if withdrawToken:
                            print(f"{bcolors.WARNING}Removendo Token{bcolors.WARNING}")
                            is_token_holder = False
                            withdrawToken = False
                        else:
                            is_token_holder = True
                            print(f"{bcolors.OKBLUE}Token recebido{bcolors.OKBLUE}")
            
            if received_packet.startswith("7777"):
                packet = received_packet.split(";")

                # Campo origem, caso o pacote de dados seja recebido por quem o originou 
                if packet[1] == machine_name:
                    packet = packet[0].split(":")

                    if packet[1] == "naoexiste":
                        print(f"{bcolors.OKBLUE}Máquina destino não se encontra na rede ou está desligada{bcolors.OKBLUE}")
                        fila.get()
                        passesToken()

                    if packet[1] == "NACK":
                        print(f"{bcolors.OKBLUE}Máquina destino identificou um erro no pacote. Retransmitindo....{bcolors.OKBLUE}")
                        retransmissionQueue.put(fila.queue[0])  # Adiciona o elemento da fila principal na fila de retransmissão
                        passesToken()

                    if packet[1] == "ACK":
                        print(f"{bcolors.OKBLUE}O pacote foi recebido corretamente pela máquina destino{bcolors.OKBLUE}")
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
            if not retransmissionQueue.empty() and retransmissionQueue.queue[0] == fila.queue[0]:
                retransmissionQueue.get()
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

            # para automatiza bastaria comentar o trecho acima e descomentar a linha abaixo
            # msg = insertFailure(dst, msg) # adiciona falha

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
                    print(f"{bcolors.FAIL }Timeout detectado. Mensagem não confirmada.{bcolors.FAIL }")
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

    # A máquina que gera o token a primeira vez deve controlá-lo
    if is_token_holder:
        # Iniciando thread para controlar o tempo do token
        time_token_control_thread = threading.Thread(target=timeTokenControl)
        time_token_control_thread.start()

    # Lógica para envio de mensagens
    while True:
        # Recebendo a entrada do usuário
        elemento = input() # exemplo "bob : Oiiii" -> "# (destino) (mensagem)"

        # Comando para adicionar Token
        if elemento == "+t":
            is_token_holder = True
            print(f"{bcolors.WARNING}Adicionando Token{bcolors.WARNING}")
        
        # Comando para remover Token
        if elemento == "-t":
            withdrawToken = True

        if fila.qsize() == 10:
            print(f"{bcolors.WARNING}Fila de mensagens cheia{bcolors.WARNING}")
        else:
            # Adicionando o elemento à fila
            fila.put(elemento)

