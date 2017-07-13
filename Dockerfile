FROM jupyter/nbviewer
USER root
RUN pip install 'newrelic>=2.88,<2.89'
USER nobody
ADD newrelic.ini newrelic.ini
