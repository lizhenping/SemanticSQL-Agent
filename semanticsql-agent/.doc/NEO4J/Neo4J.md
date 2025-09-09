docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -v /data3/lizhenping/neo4j/data:/data \
  -v /data3/lizhenping/neo4j/logs:/logs \
  -v /data3/lizhenping/neo4j/conf:/var/lib/neo4j/conf \
  -v /data3/lizhenping/neo4j/import:/var/lib/neo4j/import \
  -v /data3/lizhenping/neo4j/plugins:/var/lib/neo4j/plugins \
  -e NEO4J_AUTH=neo4j/88888888 \
  -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
  --restart unless-stopped \
  swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/neo4j:latest