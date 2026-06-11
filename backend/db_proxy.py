import socket
import threading
import sys
import time

def forward(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        src.close()
        dst.close()

def handle_client(client_socket, target_host, target_port, is_ipv6=False):
    af = socket.AF_INET6 if is_ipv6 else socket.AF_INET
    server_socket = socket.socket(af, socket.SOCK_STREAM)
    try:
        server_socket.connect((target_host, target_port))
    except Exception as e:
        print(f"Failed to connect to {target_host}:{target_port} - {e}")
        client_socket.close()
        return

    threading.Thread(target=forward, args=(client_socket, server_socket), daemon=True).start()
    threading.Thread(target=forward, args=(server_socket, client_socket), daemon=True).start()

def run_proxy(listen_port, target_host, target_port, is_ipv6=False):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(("0.0.0.0", listen_port))
    except Exception as e:
        print(f"Bind failed (port {listen_port} might be in use): {e}")
        return
        
    server.listen(10)
    print(f"Listening on 0.0.0.0:{listen_port} -> [{target_host}]:{target_port} (IPv6: {is_ipv6})", flush=True)

    while True:
        try:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client, target_host, target_port, is_ipv6), daemon=True).start()
        except Exception:
            break

def main():
    # Proxy 1: Supabase DB
    db_thread = threading.Thread(
        target=run_proxy, 
        args=(5433, "2406:da12:5ca:b700:a354:b8a4:b4d:9f64", 5432, True),
        daemon=True
    )
    
    # Proxy 2: Ollama Localhost
    ollama_thread = threading.Thread(
        target=run_proxy,
        args=(11435, "127.0.0.1", 11434, False),
        daemon=True
    )
    
    db_thread.start()
    ollama_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down proxies.")

if __name__ == "__main__":
    main()
