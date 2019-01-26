#!/usr/bin/env bats

@test "503 response when no route exist for the given host" {
  status_code=$(curl -s -o /dev/null -I -w "%{http_code}" -H "Host: i-do-not-exist" http://ceryx)
  [ $status_code -eq 503 ]
}

@test "Successful proxying when target exists" {
  curl -s -o /dev/null \
       -X POST \
       -H 'Content-Type: application/json' \
       -d '{"source": "api-route", "target": "api:5555"}' \
       http://api:5555/api/routes/

  upstream_status_code=$(curl -s -o /dev/null -I -w "%{http_code}" http://api:5555/api/routes/)
  ceryx_status_code=$(curl -s -o /dev/null -I -w "%{http_code}" -H "Host: api-route" http://ceryx/api/routes/)

  [ $ceryx_status_code -eq $upstream_status_code ]
}

@test "301 response and appropriate 'Location' header when enforce_https=true" {
  curl -s -o /dev/null \
       -X POST \
       -H 'Content-Type: application/json' \
       -d '{"source": "enforced-https-route", "target": "somewhere", "settings":{"enforce_https":true}}' \
       http://api:5555/api/routes/

  status_code=$(curl -s -o /dev/null -I -w "%{http_code}" -H "Host: enforced-https-route" http://ceryx/)

  [ $status_code -eq 301 ]
}
