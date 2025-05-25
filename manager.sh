#!/bin/bash

get_today_date() {
  date +"%Y-%m-%d"
}

teardown_containers() {
  local remove_volumes=$1
  echo "Derrubando containers do compose..."
  if [[ "$remove_volumes" == true ]]; then
    echo "Removendo volumes associados"
    docker compose down -v
  else
    docker compose down
  fi
}

remove_today_images() {
  local today
  today=$(get_today_date)
  echo "Removendo imagens criadas em: $today"

  docker images --format "{{.ID}} {{.CreatedAt}}" | \
    grep "$today" | \
    awk '{print $1}' | \
    xargs -r docker rmi
}

build_containers() {
  echo "Buildando containers..."
  docker compose build
}

start_containers() {
  echo "Subindo containers em background..."
  docker compose up -d
}

show_logs() {
  local service=$1
  if [[ -z "$service" ]]; then
    echo "Erro: informe o serviço para ver logs. Exemplo: $0 logs authentication"
    exit 1
  fi
  echo "Mostrando logs do serviço: $service (Ctrl+C para sair)"
  docker compose logs -f "$service"
}

destroy_all() {
  echo "Parando e removendo TODOS os containers..."
  docker container stop "$(docker container ls -aq)" 2>/dev/null
  docker container rm "$(docker container ls -aq)" 2>/dev/null

  echo "Removendo TODOS os volumes..."
  docker volume rm "$(docker volume ls -q)" 2>/dev/null
}

print_usage() {
  cat <<EOF
Uso: $0 <comando> [serviço]

Comandos:
  reset_all        Derruba containers e remove volumes (reset total do compose)
  reset            Derruba containers sem remover volumes (reset leve do compose)
  clean_images     Remove imagens criadas hoje
  build            Builda os containers sem subir
  start            Sobe os containers em background (sem build)
  logs <serviço>   Mostra logs do serviço especificado (ex: logs authentication)
  destroy_all      Para e remove TODOS os containers e volumes Docker do sistema

EOF
}

main() {
  if [[ $# -lt 1 ]]; then
    print_usage
    exit 1
  fi

  case "$1" in
    reset_all)
      teardown_containers true
      build_containers
      start_containers
      ;;
    reset)
      teardown_containers false
      build_containers
      start_containers
      ;;
    clean_images)
      remove_today_images
      ;;
    build)
      build_containers
      ;;
    start)
      start_containers
      ;;
    logs)
      show_logs "$2"
      ;;
    destroy_all)
      destroy_all
      ;;
    *)
      echo "Comando inválido: $1"
      print_usage
      exit 1
      ;;
  esac
}

main "$@"
