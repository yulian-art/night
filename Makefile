.PHONY: generate tools test build

tools:
	GOBIN=$(CURDIR)/.tools go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.12
	GOBIN=$(CURDIR)/.tools go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.2

generate:
	PATH="$(CURDIR)/.tools:$(PATH)" protoc -I proto --go_out=gen --go_opt=paths=source_relative --go-grpc_out=gen --go-grpc_opt=paths=source_relative proto/star/v1/star.proto

test:
	go test -race ./...

build:
	go build -o bin/star-service ./cmd/star-service
	go build -o bin/star-smoke ./cmd/star-smoke
