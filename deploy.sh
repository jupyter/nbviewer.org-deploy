#!/bin/bash
set -euo pipefail

# TODO: move this to CI, don't make assumptions about local repo checkouts

export KUBECONFIG=$PWD/secrets/ovh-kubeconfig.yaml
nbviewer_chart="../nbviewer/helm-chart/nbviewer"
echo "Is $PWD/../nbviewer up to date?"
helm dep up $nbviewer_chart

upgrade="upgrade nbviewer $nbviewer_chart -f config/nbviewer.yaml -f secrets/config/nbviewer.yaml"
helm diff -C 5 $upgrade

echo "Deploy these changes? (y|[N]) "
read confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
  echo "Upgrading..."
  helm $upgrade
else
  echo "Cancelled"
  exit 1
fi

# watch deployment rollout
kubectl rollout status -w deployment/nbviewer
