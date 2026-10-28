import json
import os
import socket
from urllib.parse import urlsplit, parse_qs

HOST = "localhost"
PORT = 8080
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

STATUS = {200: "OK", 
          400: "Bad Request", 
          404: "Not Found", 
          405: "Method Not Allowed"}
TYPES = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}


def parse_request(conn):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(1024)
        if not chunk:
            return None
        data += chunk

    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")

    method, target, _ = lines[0].split(" ")
    url = urlsplit(target)
    query = {k: v[0] for k, v in parse_qs(url.query).items()}

    headers = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()

    length = int(headers.get("content-length", 0))
    while len(body) < length:
        body += conn.recv(1024)

    return method, url.path, query, headers, body


def make_response(status, body, content_type="text/html"):
    if isinstance(body, str):
        body = body.encode()
    head = (
        f"HTTP/1.1 {status} {STATUS[status]}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return head.encode() + body


def json_response(status, data):
    return make_response(status, json.dumps(data, indent=2), "application/json")


def handle(method, path, query, headers, body):
    if path == "/page" and method == "GET":
        return make_response(200, f"<h1>Page {query.get('id')}</h1><p>Query: {query}</p>")

    if path == "/headers" and method == "GET":
        return json_response(200, {"method": method, "path": path, "query": query, "headers": headers})
    
    if path == "/api/echo":
        if method != "POST":
            return json_response(405, {"error": "Use POST"})
        try:
            data = json.loads(body)
        except ValueError:
            return json_response(400, {"error": "Invalid JSON"})
        return json_response(200, {"received": data})

    if method == "GET":
        if path == "/":
            path = "/index.html"
        file_path = os.path.join(PUBLIC_DIR, path.lstrip("/"))
        if ".." in path or not os.path.isfile(file_path):
            return json_response(404, {"error": "Not found"})
        with open(file_path, "rb") as f:
            content_type = TYPES.get(os.path.splitext(file_path)[1], "text/plain")
            return make_response(200, f.read(), content_type)

    return json_response(405, {"error": "Method not allowed"})


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server running on http://{HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        try:
            request = parse_request(conn)
            if request:
                print(request[0], request[1])
                conn.sendall(handle(*request))
        except Exception:
            conn.sendall(json_response(400, {"error": "Bad request"}))
        finally:
            conn.close()


if __name__ == "__main__":
    main()