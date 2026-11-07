Primeira versão estável do **Clips — Mascote do PC**, para Debian/Ubuntu Linux e Windows 10/11 de 64 bits (amd64/x86_64).

- Oito mascotes: Clippy, Pretí, Marla, Mochi, Louro José, Zoe, Mixo e Mixi.
- Reações aos cliques, descanso após inatividade e acompanhamento do cursor.
- Arrastar, espelhar, pausar, trocar de personagem e salvar preferências.
- Menu na bandeja e opção de iniciar com o computador.
- Executável independente, com Python, PyQt5 e imagens incluídos.
- Funciona offline.

### Windows 10/11

Baixe **`clips-1.0-windows-x86_64.exe`** e abra com dois cliques. Não precisa instalar Python ou PyQt5. O arquivo `clips-1.0-windows-x86_64.zip` inclui o executável, o README e a licença.

O executável Windows foi compilado e testado no GitHub Actions com Windows Server 2022; ainda não houve teste manual em Windows 10/11.

Para verificar a integridade no PowerShell, compare `Get-FileHash .\clips-1.0-windows-x86_64.exe -Algorithm SHA256` com `SHA256SUMS-windows.txt`.

### Linux — download e execução

Baixe **`clips-1.0-linux-x86_64`** nos arquivos desta release. Na pasta do download:

```bash
chmod +x clips-1.0-linux-x86_64
./clips-1.0-linux-x86_64
```

O arquivo **`clips-1.0-linux-x86_64.tar.gz`** contém o mesmo executável, já com permissão de execução, o README e a licença. Extraia o pacote e abra o executável.

**Compatibilidade:** Debian 12 ou mais recente e Ubuntu 22.04 ou mais recente, amd64/x86_64, em sessão gráfica **X11/Xorg**. Wayland não é suportado. Não é necessário instalar Python ou PyQt5. Esta release não contém executáveis para ARM.

Para conferir a integridade, baixe também `SHA256SUMS` e execute `sha256sum --ignore-missing --check SHA256SUMS` na pasta dos downloads.

Para encerrar, clique com o botão direito no mascote e escolha **Sair**.

Distribuído sob GPL-3.0-or-later. O código-fonte do executável Linux está na tag `v1.0`. O código-fonte do build Windows está em `clips-1.0-windows-source.zip`, com os ajustes de empacotamento para Windows; o commit exato é informado abaixo.
