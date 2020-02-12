FROM jupyter/nbviewer
USER root
RUN pip install 'newrelic==5.6.0.135'
USER nobody
ADD newrelic.ini newrelic.ini
