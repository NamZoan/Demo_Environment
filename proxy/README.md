# Private Boxphone SOCKS5 proxy

This is a standalone, authenticated SOCKS5 proxy. It is separate from the
website services and supports TCP `CONNECT` only.

Runtime configuration is kept in `runtime.env` (ignored by Git):

```text
PROXY_USERS=user1:password1,user2:password2
PROXY_HOST=0.0.0.0
PROXY_PORT=18080
```

Start it in the background from the repository root:

```bash
nohup proxy/start.sh > proxy/proxy.log 2>&1 &
echo $! > proxy/proxy.pid
```

Configure Boxphone with:

```text
Type: SOCKS5
Host: 161.248.81.149
Port: 18080
Username: one configured username
Password: matching value from PROXY_USERS
```

Do not remove authentication or expose the credentials in a public channel.
Because this environment does not grant root firewall access, restrict TCP
port 18080 at the VPS provider firewall to the Boxphone source IPs when
possible.
