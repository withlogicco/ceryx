#------------ bootstrap the cluster nodes --------------------

start_cmd='redis-server --port 6379 --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes'
redis_image='redis:5.0'
network_name='redis_cluster_net'

docker network create $network_name
echo $network_name " created"


#---------- remove existing containers with same name -------------------
for i in `seq 6379 6384`; do 
    docker stop redis-${i}
    docker rm redis-${i}
done
unset i

#---------- create the cluster ------------------------

for port in `seq 6379 6384`; do 
 docker run -d --name "redis-"$port -p $port:6379 --net $network_name $redis_image $start_cmd;
 echo "created redis cluster node redis-"$port
done
unset port

cluster_hosts=''

for port in `seq 6379 6384`; do 
 hostip=`docker inspect -f '{{(index .NetworkSettings.Networks "redis_cluster_net").IPAddress}}' "redis-"$port`;
 echo "IP for cluster node redis-"$port "is" $hostip
 cluster_hosts="$cluster_hosts$hostip:6379 ";
done
unset port

echo "cluster hosts "$cluster_hosts
echo "creating cluster...."
echo 'yes' | docker run -i --rm --net $network_name $redis_image redis-cli --cluster create $cluster_hosts --cluster-replicas 1;