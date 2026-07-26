# Build  Worker .NET ---
FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build
WORKDIR /source
COPY . .
RUN dotnet restore
RUN dotnet publish -c Release -o /app --no-restore


FROM mcr.microsoft.com/dotnet/runtime:7.0

# Installer Redis Server
USER root
RUN apt-get update && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root pour la sécurité 
RUN useradd -m -u 10001 appuser

WORKDIR /app
COPY --from=build /app .


RUN chown -R appuser:appuser /app /var/lib/redis /var/log/redis


USER appuser


EXPOSE 6379


CMD redis-server --daemonize yes --protected-mode no --bind 0.0.0.0 && dotnet Worker.dll