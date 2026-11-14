#!/bin/sh
# Lab Part 2: Week 1's network by hand (namespaces, veth pairs, a bridge). Run in the course container.
set -x
ip netns add red
ip netns add blue
ip link add veth-red type veth peer name red-br
ip link add veth-blue type veth peer name blue-br
ip link set veth-red netns red
ip link set veth-blue netns blue
ip link add br0 type bridge
ip link set red-br master br0
ip link set blue-br master br0
ip link set br0 up
ip link set red-br up
ip link set blue-br up
ip netns exec red ip addr add 10.3.9.1/24 dev veth-red
ip netns exec red ip link set veth-red up
ip netns exec blue ip addr add 10.3.9.2/24 dev veth-blue
ip netns exec blue ip link set veth-blue up
ip netns exec red ping -c 2 10.3.9.2
bridge fdb show br br0
