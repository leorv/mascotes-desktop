Primeira versão estável do **Clips — Mascote do PC**, para Debian/Ubuntu Linux de 64 bits (amd64/x86_64).

- Oito mascotes: Clippy, Pretí, Marla, Mochi, Louro José, Zoe, Mixo e Mixi.
- Reações aos cliques, descanso após inatividade e acompanhamento do cursor.
- Arrastar, espelhar, pausar, trocar de personagem e salvar preferências.
- Menu na bandeja e opção de iniciar com o computador.
- Executável independente, com Python, PyQt5 e imagens incluídos.
- Funciona offline.

### Download e execução

Baixe **`clips-1.0-linux-x86_64`** nos arquivos desta release. Na pasta do download:

```bash
chmod +x clips-1.0-linux-x86_64
./clips-1.0-linux-x86_64
```

O arquivo **`clips-1.0-linux-x86_64.tar.gz`** contém o mesmo executável, já com permissão de execução, o README e a licença. Extraia o pacote e abra o executável.

**Compatibilidade:** Debian 12 ou mais recente e Ubuntu 22.04 ou mais recente, amd64/x86_64, em sessão gráfica **X11/Xorg**. Wayland não é suportado. Não é necessário instalar Python ou PyQt5. Esta release não contém executáveis para Windows ou ARM.

Para conferir a integridade, baixe também `SHA256SUMS` e execute `sha256sum --ignore-missing --check SHA256SUMS` na pasta dos downloads.

Para encerrar, clique com o botão direito no mascote e escolha **Sair**.

Distribuído sob GPL-3.0-or-later. O código-fonte correspondente está na tag `v1.0`, disponível nos arquivos de código-fonte desta release.
