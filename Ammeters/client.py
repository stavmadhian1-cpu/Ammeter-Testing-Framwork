from socket import socket, AF_INET, SOCK_STREAM


def request_current_from_ammeter(port: int, command: bytes):
    with socket(AF_INET, SOCK_STREAM) as s:
        s.connect(('localhost', port))
        s.sendall(command)
        data = s.recv(1024)
        if data:
            print(f"Received current measurement from port {port}: {data.decode('utf-8')} A")
        else:
            print("No data received.")


def read_current_from_ammeter(port: int, command: bytes, timeout: float = 2.0) -> float:
    """
    Requests one current measurement and returns it as a float.
    Raises OSError if the ammeter can't be reached in time, or ValueError if it sends no valid value.
    """
    with socket(AF_INET, SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(('localhost', port))
        s.sendall(command)
        data = s.recv(1024)
    if not data:
        raise ValueError(f"No data received from port {port}")
    return float(data.decode('utf-8'))

