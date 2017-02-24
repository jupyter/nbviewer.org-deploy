FROM jupyter/nbviewer
USER root
RUN pip install 'newrelic<2.80'
USER nobody
ADD newrelic.ini newrelic.ini
