FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim@sha256:237133a0ea20cffcfaa92588e1c8a56d58fe99f44da72dcff35aeb017119abcf AS build
WORKDIR /src
COPY source/ ./
RUN --network=none dotnet publish CtYun.csproj -c Release -o /out --self-contained false -p:PublishAot=false -p:NuGetAudit=false && dotnet /out/CtYun.dll self-test

FROM mcr.microsoft.com/dotnet/runtime:8.0-bookworm-slim@sha256:d0eda6432ed68938bda26f2edf230db10ee2bcaf3f3249ee8e73f9b9f0173fc9
WORKDIR /app
COPY --from=build /out/ ./
COPY LICENSE.upstream ./LICENSE.upstream
USER 1654:1654
ENV DOTNET_EnableDiagnostics=0 DOTNET_CLI_TELEMETRY_OPTOUT=1
ENTRYPOINT ["dotnet", "/app/CtYun.dll"]
CMD ["run"]
