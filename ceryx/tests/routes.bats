#!/usr/bin/env bats

@test "addition using bc" {
  http http://localhost:5555/api/routes
}

@test "addition using dc" {
  # result="$(echo 2 2+p | dc)"
  # [ "$result" -eq 4 ]
}
