workflow "Main" {
  on = "push"
  resolves = ["test"]
}


action "test" {
  uses = "./actions/test"
}