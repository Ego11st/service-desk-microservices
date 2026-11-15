FROM alpine:3.22
RUN apk add --no-cache iptables
COPY rules.sh /rules.sh
ENTRYPOINT ["sh", "/rules.sh"]
