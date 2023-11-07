import socket
import threading
import time
import json
from queue import Queue

# Estrutura do pacote de dados
class DataPacket:
    def __init__(self, control_error, source, destination, message): # Inserir CRC
        self.control_error = control_error
        self.source = source
        self.destination = destination
        #self.crc = crc
        self.message = message

    def to_string(self):
        return f"7777:{self.control_error};{self.source}:{self.destination};{self.message}"

def process_message(packet):
    packet = packet.split(";")

    src = packet[1]
    dst = packet[2]
    msg = packet[3]

    if dst == machine_name: # Pacote pra mim
        ## if Calculo CRC ok ##
        print("* Mensagem recebida, CRC ok. *")
        
        print(f"MENSAGEM DE {src}: '{msg}' ")
        
        print("* Enviando ACK... *")

        err = "ACK"
    
        # else -> crc errado, enviando nack...#
        #   err = "NACK"

        packet = DataPacket(err, dst, src, msg)
        
    else: # Nao eh pra mim, repassando... 
        packet = DataPacket("naoexiste", src, dst, msg)

     ## a nao ser que repassando
    packet_str = packet.to_string()
    client_socket.sendto(packet_str.encode(), (src, port))

# Implementação do servidor para receber e processar mensagens
def receive_message(token_destination, machine_name, token_time, is_token_holder):
    # Código para a lógica do servidor usando sockets UDP
    # Criação e configuração do socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((socket.gethostname(), port))

    while True:
        # Recebendo pacotes
        data, addr = server_socket.recvfrom(1024)
        received_packet = data.decode('utf-8')

        # Lógica para manipular os pacotes recebidos
        # verifica se é o token
        if received_packet.startswith("9000"):
           if not fila.empty():
               send_message(fila.get())

        if received_packet.startswith("7777"):
              process_message(received_packet)

# Função para enviar mensagens
def send_message(message):

    if is_token_holder and not fila.empty():
        # Código para enviar mensagens
        dst_data = fila.get().split(" ")
        data_packet = DataPacket("naoexiste", machine_name, dst_data[1], dst_data[3])
        packet_string = data_packet.to_string()
        client_socket.sendto(packet_string.encode(), (token_dest, port))

        #agora tem que esperar o retorno


# Leitura do arquivo de configuração GPT então tem que ver
def read_config_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        token_destination = lines[0].strip()
        machine_name = lines[1].strip()
        token_time = int(lines[2].strip())
        is_token_holder = lines[3].strip()
        return token_destination, machine_name, token_time, is_token_holder

if __name__ == '__main__':
    global client_socket
    global port
    global fila
    global is_token_holder

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = 8080
    fila = Queue()

    # Carregando configurações do arquivo
    token_dest, machine_name, token_time, is_token_holder = read_config_file('config.txt')

    # Iniciando para receber menssagens
    receive_message_thread = threading.Thread(target=receive_message, args=(token_dest, machine_name, token_time, is_token_holder))
    receive_message_thread.start()

    # Iniciando para enviar menssagens
    send_message_thread = threading.Thread(target=send_message, args=(token_dest, machine_name))
    send_message_thread.start()

    # Lógica para envio de mensagens
    while True:
        # Recebendo a entrada do usuário
        elemento = input("# ")
        # Adicionando o elemento à fila
        fila.put(elemento)
