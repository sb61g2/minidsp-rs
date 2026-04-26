{ pkgs }: 

pkgs.runCommand "foo" { } "echo 'hi there'"
