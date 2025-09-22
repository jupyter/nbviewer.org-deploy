#!/bin/bash
set -euo pipefail

# TODO: move this to CI, don't make assumptions about local repo checkouts

export KUBECONFIG=$PWD/secrets/ovh-kubeconfig.yaml

nbviewer_chart="${NBVIEWER_CHART:-../nbviewer/helm-chart/nbviewer}"
echo "Is $nbviewer_chart up to date?"
helm dep up $nbviewer_chart

upgrade="upgrade nbviewer $nbviewer_chart -f config/nbviewer.yaml -f secrets/config/nbviewer.yaml"

if [[ -z "${CI:-}" ]]; then
  helm diff -C 5 $upgrade
  echo "Deploy these changes? (y|[N]) "
  read confirm

  if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo "confirmed"
  else
    echo "Cancelled"
    exit 1
  fi
fi

echo "Upgrading..."
helm $upgrade --cleanup-on-fail

# watch deployment rollout
kubectl rollout status -w deployment/nbviewer
