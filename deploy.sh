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

# Deploy to Cloud Run
echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
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

echo ""
echo "To view logs:"
echo "  gcloud run logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
echo ""
echo "To redeploy after code changes:"
echo "  ./deploy.sh ${REGION} ${SERVICE_NAME}"
