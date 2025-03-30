import socket
import threading
from concurrent.futures import ThreadPoolExecutor

tcp_clients = []
udp_clients = set()
clients_lock = threading.Lock()
clients_nicknames = {}

MAX_THREADS = 10


def handle_tcp_client(conn, address):
    try:
        nickname = conn.recv(1024).decode('cp1250')
        print(f"Connected user: {nickname} on address {address}")

        with clients_lock:
            clients_nicknames[address] = nickname

        while True:
            msg = conn.recv(1024).decode('cp1250')
            if not msg:
                break
            print(f"[TCP-server] Received message from {nickname}: {msg}")
            for client in tcp_clients[:]:
                if client[0] != conn:
                    try:
                        client[0].sendall(bytes(f"{nickname}: {msg}", 'cp1250'))
                    except Exception as exception:
                        print(f"Error sending message to {client[1]}: {exception}")
                        if client in tcp_clients:
                            tcp_clients.remove(client)

    except Exception as ex:
        print(f"Error: {ex}. Client address: {address}")
    finally:
        print(f"Closing connection for address: {address}")
        conn.close()
        with clients_lock:
            if (conn, address) in tcp_clients:
                tcp_clients.remove((conn, address))
            udp_clients.discard(address)
            clients_nicknames.pop(address, None)


def handle_udp_messages(server_udp_socket):
    while True:
        buff, address = server_udp_socket.recvfrom(1024)
        msg = buff.decode('cp1250')

        nickname = clients_nicknames.get(address, f"Unknown-{address}")

        udp_message = f"{nickname}: {msg}"

        print(f"[UDP-server] Received message from {nickname}: {msg}")

        for client_address in udp_clients:
            if client_address != address:
                try:
                    server_udp_socket.sendto(udp_message.encode('cp1250'), client_address)
                except Exception as exception:
                    print(f"Error sending UDP message to {client_address}: {exception}")
                    udp_clients.remove(client_address)


def main():
    server_port = 9009

    # TCP socket
    server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_tcp_socket.bind(('', server_port))
    server_tcp_socket.listen(5)

    # UDP socket
    server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_udp_socket.bind(('', server_port))

    print('SERVER STARTED')

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        executor.submit(handle_udp_messages, server_udp_socket)

        try:
            while True:
                conn_accepted, address_accepted = server_tcp_socket.accept()
                with clients_lock:
                    tcp_clients.append((conn_accepted, address_accepted))
                    udp_clients.add(address_accepted)

                executor.submit(handle_tcp_client, conn_accepted, address_accepted)
        except Exception as e:
            print(f"Error: {e}. Can't accept connection")
        finally:
            server_tcp_socket.close()
            server_udp_socket.close()


if __name__ == "__main__":
    main()
