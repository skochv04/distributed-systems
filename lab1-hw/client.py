import socket
import struct
import threading
from art import art

close_flag = False

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9009

MULTICAST_GROUP = "229.1.2.3"
MULTICAST_PORT = 9000


def generate_random_ascii():
    return art("random")


def print_action_list():
    print("\nPossible actions:")
    print("T - Send text message")
    print("U - Send ASCII picture using UDP")
    print("M - Send ASCII picture using multicast")
    print("Q - Exit")


def send_udp_picture(client_udp):
    ascii_art = generate_random_ascii()
    client_udp.sendto(ascii_art.encode('cp1250'), (SERVER_IP, SERVER_PORT))
    print("[UDP] Sent ASCII Art to the server")


def send_multicast_picture(client_multicast, user_nick):
    ascii_art = generate_random_ascii()
    message = f"{user_nick}: {ascii_art}"
    client_multicast.sendto(message.encode('cp1250'), (MULTICAST_GROUP, MULTICAST_PORT))
    print("[Multicast] Sent ASCII Art to the multicast group")


def send_text_message(client):
    print("*** Chat mode activated. Type '/menu' to go back to menu")
    print("Enter your message:")
    while True:
        msg_input = input()
        if msg_input.strip().lower() == '/menu':
            print("\nWe are back to menu. Enter your choice: ")
            return
        client.sendall(bytes(msg_input, 'cp1250'))


def receive_tcp_messages(client):
    global close_flag
    while not close_flag:
        try:
            msg = client.recv(1024).decode('cp1250')
            if not msg:
                break
            print(f"[TCP] {msg}")
        except Exception as e:
            print(f"Error receiving TCP message: {e}")
            break

    print("Receive TCP thread exiting...")


def receive_udp_messages(client_udp):
    global close_flag
    while not close_flag:
        try:
            msg, _ = client_udp.recvfrom(1024)
            print(f"[UDP]: {msg.decode('cp1250')}")
        except Exception as e:
            print(f"Error receiving UDP message: {e}")
            break

    print("Receive UDP thread exiting...")


def receive_multicast_messages(client_multicast, user_nick):
    global close_flag
    while not close_flag:
        try:
            msg, _ = client_multicast.recvfrom(1024)
            message = msg.decode('cp1250')
            if not message.startswith(f"{user_nick}:"):
                print(f"[Multicast]: {message}")
        except Exception as e:
            print(f"Error receiving multicast message: {e}")
            break

    print("Receive Multicast thread exiting...")


def main():
    global close_flag

    user_nick = ""
    while len(user_nick) < 3:
        user_nick = input("Enter your nickname (at least 3 characters): ").strip()
        if len(user_nick) < 3:
            print("Nickname must be at least 3 characters long.\n")

    print('CLIENT STARTED')

    # TCP socket
    client_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_tcp.connect((SERVER_IP, SERVER_PORT))
    client_tcp.sendall(bytes(user_nick, 'cp1250'))

    # UDP socket
    tcp_port = client_tcp.getsockname()[1]
    client_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_udp.bind(('', tcp_port))

    # Multicast socket
    client_multicast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_multicast.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_multicast.bind(('', MULTICAST_PORT))

    # Attach to multicast group
    multicast_request = struct.pack("4sL", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    client_multicast.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, multicast_request)

    print_action_list()

    print("Enter your choice: ")

    receive_tcp_thread = threading.Thread(target=receive_tcp_messages, args=(client_tcp,), daemon=True)
    receive_tcp_thread.start()

    receive_udp_thread = threading.Thread(target=receive_udp_messages, args=(client_udp,), daemon=True)
    receive_udp_thread.start()

    receive_multicast_thread = threading.Thread(target=receive_multicast_messages, args=(client_multicast, user_nick),
                                                daemon=True)
    receive_multicast_thread.start()

    while not close_flag:

        choice = input().strip().upper()

        if choice == 'T':
            send_text_message(client_tcp)
        elif choice == 'U':
            send_udp_picture(client_udp)
        elif choice == 'M':
            send_multicast_picture(client_multicast, user_nick)
        elif choice == 'Q':
            print("Closing connection...")
            close_flag = True
            break
        else:
            print("Invalid choice. Please try again.")

    client_tcp.close()
    client_udp.close()
    client_multicast.close()
    receive_tcp_thread.join()
    receive_udp_thread.join()
    receive_multicast_thread.join()


if __name__ == "__main__":
    main()
