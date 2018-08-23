FROM jupyter/nbviewer
USER root
RUN pip install 'newrelic==3.2.0.91' 'tornado<5'
USER nobody
ADD newrelic.ini newrelic.ini
