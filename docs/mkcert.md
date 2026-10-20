# Creating the HTTPS certificate with mkcert

This guide creates the certificate that Git Local uses for HTTPS, with
[mkcert](https://github.com/FiloSottile/mkcert). mkcert creates a local certificate
authority (CA) on your computer and signs the certificate with it. Devices that
trust that CA accept the certificate without warnings.

The certificate must cover every name and address you use to open the server:

| Name | Used for |
|---|---|
| `git.local` | computers on the network (`https://git.local/`) |
| `192.168.0.2` | phones and computers by IP (`https://192.168.0.2:8080/`) |
| `localhost` | this computer |

Replace `192.168.0.2` with the fixed address of your computer.

## 1. Install mkcert

On Arch Linux:

```sh
sudo pacman -S --needed mkcert nss
```

`nss` is needed so that mkcert can install the CA in Firefox and Chromium.

## 2. Create the local CA (once per computer)

```sh
mkcert -install
```

This creates the CA and installs it in the system trust store and in the browsers
it finds. Find the CA files with:

```sh
mkcert -CAROOT
```

The output is a folder such as `/home/<user>/.local/share/mkcert`. It contains
`rootCA.pem` (the public CA certificate) and `rootCA-key.pem` (the CA private key).
**Keep `rootCA-key.pem` secret**: anyone with it can sign certificates that your
devices trust. Do not copy it to the project or to other devices.

## 3. Create the server certificate

From the project root, write the certificate and the private key into `src/cert/`:

```sh
mkcert -cert-file src/cert/git.local.pem \
       -key-file  src/cert/git.local-key.pem \
       git.local 192.168.0.2 localhost
```

mkcert prints the file names and the expiry date (about 3 years).

The private key (`git.local-key.pem`) is listed in `.gitignore` and must not be
committed. `git.local.pem` is public and may be committed.

## 4. Check the certificate

```sh
openssl x509 -in src/cert/git.local.pem -noout -subject -issuer -enddate
openssl x509 -in src/cert/git.local.pem -noout -ext subjectAltName
```

The `subjectAltName` line must list `DNS:git.local`, `DNS:localhost` and
`IP Address:192.168.0.2`.

Check that the key matches the certificate (the two hashes must be equal):

```sh
openssl x509 -in src/cert/git.local.pem -noout -pubkey | sha256sum
openssl pkey  -in src/cert/git.local-key.pem -pubout    | sha256sum
```

## 5. Install it on the server

`make install` copies `src/cert/*.pem` to `<root>/git.local/cert/`, with
permissions `600` for the key and `644` for the certificate. nginx reads them from
there. If the key is missing, the installer warns you and HTTPS does not start.

After changing the certificate, run `make install` again, then check nginx:

```sh
sudo nginx -t
```

## 6. Trust the CA on other devices

Each device that opens the server must trust **the CA** (`rootCA.pem`), not the
server certificate. Copy `rootCA.pem` from `mkcert -CAROOT` to the device.

**Linux (other computers)**

```sh
sudo cp rootCA.pem /etc/ca-certificates/trust-source/anchors/mkcert-rootCA.pem
sudo trust extract-compat
```

**Windows**

Double-click `rootCA.pem`, choose *Install certificate*, select *Local machine*,
then *Place all certificates in the following store* → *Trusted Root Certification
Authorities*.

**iPhone / iPad**

Send `rootCA.pem` to the device (e-mail, AirDrop or a file server) and open it.
Install the profile in *Settings → General → VPN & Device Management*. Then enable
full trust in *Settings → General → About → Certificate Trust Settings*.

**Android**

Copy `rootCA.pem` to the phone. Go to *Settings → Security → Encryption and
credentials → Install a certificate → CA certificate* and select the file. Android
shows a warning about user certificates; that is expected for a private CA.

Firefox keeps its own store: import `rootCA.pem` in *Settings → Privacy & Security
→ Certificates → View Certificates → Authorities → Import*, unless it reads the
system store.

## 7. Use the client script with the CA

The `git.local` client script uses the system trust store by default. If the CA is
not installed in the system, point the script to it:

```sh
export GITLOCAL_CACERT="$(mkcert -CAROOT)/rootCA.pem"
```

## Renewing and replacing

- The certificate expires after about 3 years. Repeat step 3, then `make install`.
- Keep the same CA (`mkcert -install` is only needed once). Devices that already
  trust the CA keep trusting the new certificate.
- If you delete the CA (`mkcert -uninstall`) or create a new one, every device must
  trust the new `rootCA.pem` again.

## Troubleshooting

- **Browser shows "not secure" or "name mismatch"**: the device does not trust the
  CA, or the address is not in the certificate. Check step 4.
- **`curl: (60) SSL certificate problem`**: use `curl --cacert "$(mkcert -CAROOT)/rootCA.pem" https://git.local/`.
- **nginx does not start**: check that `<root>/git.local/cert/` has both files and
  that `sudo nginx -t` passes.
- **Phone warns only for the IP**: the certificate must contain `192.168.0.2` (step 4).
