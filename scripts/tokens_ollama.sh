#!/usr/bin/env bash
# Tokens y tiempo de cada consulta a Ollama, leídos del registro del servicio (VM-IA).
#   bash tokens_ollama.sh            -> consultas de hoy
#   bash tokens_ollama.sh "-2 hours" -> de las últimas 2 horas
# entrada = tokens que leyó el modelo (instrucciones + noticia); salida = tokens que escribió.
# En CPU el tiempo depende sobre todo de la salida (unos 2,5 tokens por segundo con qwen3:14b).
DESDE="${1:-today}"
journalctl -u ollama --since "$DESDE" --no-pager -o short-iso | perl -MTime::Piece -ne '
  if (/^(\S+?)[+-]\d\d:?\d\d .*task (\d+) \| new prompt.*task\.n_tokens = (\d+)/) { $i{$2}=$1; $e{$2}=$3 }
  elsif (/^(\S+?)[+-]\d\d:?\d\d .*task (\d+) \| stop processing: n_tokens = (\d+)/ && exists $e{$2}) {
    my $s = Time::Piece->strptime($1,"%Y-%m-%dT%H:%M:%S") - Time::Piece->strptime($i{$2},"%Y-%m-%dT%H:%M:%S");
    printf "%s UTC  entrada=%5d  salida=%4d  segundos=%4d\n", $i{$2}, $e{$2}, $3-$e{$2}, $s; delete $e{$2} }'
