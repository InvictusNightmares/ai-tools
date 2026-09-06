FROM ghcr.io/browserless/chrome:v2.56.2@sha256:1be15d1e3bad53e89d07ef529a52615739f77b7cd997a49c0ec97aaa78d0fcaf
USER root
# Remove actual optional CJK font packages; retain English and Unicode fallback.
# No browser fingerprint emulation or navigator/font API overrides.
RUN dpkg --purge --force-depends fonts-noto-cjk fonts-wqy-zenhei \
    && fc-cache -f \
    && ! fc-list : family | grep -E 'Noto (Sans|Serif).*CJK|WenQuanYi'
USER blessuser
