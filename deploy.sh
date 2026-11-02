#!/bin/bash

# BottosCon Deployment Script for Google Cloud Run
# Usage: ./deploy.sh [region] [service-name]
# Example: ./deploy.sh us-central1 bottoscon-app

set -e

# Configuration
PROJECT_ID="bottoscon"
SERVICE_NAME="${2:-bottoscon-app}"
REGION="${1:-northamerica-northeast1}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "=========================================="
echo "BottosCon Deployment to Google Cloud Run"
echo "=========================================="
echo "Project ID: ${PROJECT_ID}"
echo "Service Name: ${SERVICE_NAME}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE_NAME}"
echo ""

# Check if gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed."
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo "Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "Enabling required Google Cloud APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build the Docker image using Cloud Build
echo ""
echo "Building Docker image with Cloud Build..."
gcloud builds submit --tag ${IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo "Error: Cloud Build failed."
    exit 1
fi

# Table-schedule sheet URLs are secrets (the organizers' workbook may be editable
# by anyone with the link). They are never stored in the repo: export them in
# your shell before deploying. Once set on the service they persist across
# redeploys, so they only need to be exported again when they change.
ENV_ARGS=()
if [ -n "${TABLE_USAGE_CSV_URL}" ] && [ -n "${ORGANIZER_GAMES_CSV_URL}" ]; then
    ENV_ARGS=(--update-env-vars "TABLE_USAGE_CSV_URL=${TABLE_USAGE_CSV_URL},ORGANIZER_GAMES_CSV_URL=${ORGANIZER_GAMES_CSV_URL}")
else
    echo "Note: TABLE_USAGE_CSV_URL / ORGANIZER_GAMES_CSV_URL not set in this shell; leaving the service's existing values unchanged."
fi

# Deploy to Cloud Run
echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME}     "${ENV_ARGS[@]}" \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 3600 \
    --max-instances 100

if [ $? -ne 0 ]; then
    echo "Error: Cloud Run deployment failed."
    exit 1
fi

echo ""
echo "=========================================="
echo "Deployment successful!"
echo "=========================================="
echo ""
echo "Your app is now live!"
echo "Service URL:"
gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)'

# Every deploy leaves behind a Cloud Run revision and a container image, and the
# images are billed for storage. Count them and, if there are too many, print
# cleanup instructions. This only counts and prints; it never deletes anything.
KEEP_VERSIONS=5
CLEANUP_THRESHOLD=10
IMAGE_COUNT=$(gcloud container images list-tags ${IMAGE_NAME} --format='get(digest)' 2>/dev/null | grep -c . || true)
REVISION_COUNT=$(gcloud run revisions list --service ${SERVICE_NAME} --region ${REGION} --format='value(metadata.name)' 2>/dev/null | grep -c . || true)
echo ""
echo "Stored versions: ${REVISION_COUNT} Cloud Run revisions, ${IMAGE_COUNT} container images"
if [ "${IMAGE_COUNT:-0}" -ge ${CLEANUP_THRESHOLD} ] || [ "${REVISION_COUNT:-0}" -ge ${CLEANUP_THRESHOLD} ]; then
    echo ""
    echo "!! ${CLEANUP_THRESHOLD} or more old versions are stored. Old container images are billed for storage."
    echo "   To keep only the newest ${KEEP_VERSIONS} of each, run these (revisions first, then images):"
    echo ""
    echo "   gcloud run revisions list --service ${SERVICE_NAME} --region ${REGION} \\"
    echo "       --sort-by=~metadata.creationTimestamp --format='value(metadata.name)' \\"
    echo "       | tail -n +$((KEEP_VERSIONS + 1)) | tr -d '\r' \\"
    echo "       | xargs -r -n1 gcloud run revisions delete --region ${REGION} --quiet"
    echo ""
    echo "   gcloud container images list-tags ${IMAGE_NAME} \\"
    echo "       --sort-by=~timestamp --format='get(digest)' \\"
    echo "       | tail -n +$((KEEP_VERSIONS + 1)) | tr -d '\r' \\"
    echo "       | xargs -r -I{} gcloud container images delete ${IMAGE_NAME}@{} --force-delete-tags --quiet"
    echo ""
    echo "   (Cloud Run refuses to delete the revision serving traffic, and the newest ${KEEP_VERSIONS} images"
    echo "   are the ones behind the newest ${KEEP_VERSIONS} revisions, so the live app is not affected.)"
fi

echo ""
echo "To view logs:"
echo "  gcloud run logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
echo ""
echo "To redeploy after code changes:"
echo "  ./deploy.sh ${REGION} ${SERVICE_NAME}"
