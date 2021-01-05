# syntax=docker/dockerfile:experimental
FROM centos:7

RUN yum update -y && yum install python-setuptools MySQL-python -y

WORKDIR /app
ENV PYTHONPATH /app
ENV MODULE_QUERY_HOST db
ENV MODULE_QUERY_DB p3
ENV MODULE_QUERY_USER p3
ENV MODULE_QUERY_PASSWD p3

CMD python setup.py install && /bin/bash
