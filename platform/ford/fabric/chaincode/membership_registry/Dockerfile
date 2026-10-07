FROM golang:1.21-alpine AS builder
WORKDIR /chaincode
COPY membership_registry.go .
COPY go.mod .
COPY go.sum .
RUN go build -o /chaincode/membership-registry .

FROM alpine:3.19
RUN addgroup -S fabric && adduser -S fabric -G fabric
COPY --from=builder /chaincode/membership-registry /usr/local/bin/membership-registry
RUN chown fabric:fabric /usr/local/bin/membership-registry
USER fabric
ENV CHAINCODE_SERVER_ADDRESS=0.0.0.0:9999
EXPOSE 9999
CMD ["/usr/local/bin/membership-registry"]
