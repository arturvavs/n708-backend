#!/bin/bash

# Define a data de hoje no formato usado pelo Docker
get_today_date() {
  date +"%Y-%m-%d"
}

# Para e remove containers, redes e volumes
teardown_containers() {
  echo "Derrubando containers e removendo volumes..."
  docker compose down -v
}

# Remove imagens criadas hoje
remove_today_images() {
  local today
  today=$(get_today_date)
  echo "Removendo imagens criadas em: $today"

  docker images --format "{{.ID}} {{.CreatedAt}}" | \
    grep "$today" | \
    awk '{print $1}' | \
    xargs -r docker rmi
}

# Sobe os containers novamente
start_containers() {
  echo "Subindo containers..."
  docker compose up -d
}

# Execução principal
main() {
  teardown_containers
  remove_today_images
  start_containers
}

main
