#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---

# Get Project ID from gcloud config
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "Google Cloud project ID not found. Please set it using 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi
echo "Using Google Cloud Project: $PROJECT_ID"

# Prompt for Service Name with a default value
DEFAULT_SERVICE_NAME="imagen-studio"
read -p "Enter the Cloud Run service name [default: $DEFAULT_SERVICE_NAME]: " SERVICE_NAME
SERVICE_NAME=${SERVICE_NAME:-$DEFAULT_SERVICE_NAME}

# Prompt for Region with a default value
DEFAULT_REGION="asia-south1"
read -p "Enter the deployment region [default: $DEFAULT_REGION]: " REGION
REGION=${REGION:-$DEFAULT_REGION}

# --- Deployment Type ---
DEPLOYMENT_TYPE=""
read -p "Is this a fresh deployment or a re-deployment? (fresh/re-deploy): " DEPLOYMENT_TYPE

if [[ "$DEPLOYMENT_TYPE" == "fresh" ]]; then
    # --- Google Cloud Storage Bucket Setup ---
    IMAGE_CREATION_BUCKET=""
    read -p "Do you have an existing Google Cloud Storage bucket for this app? (y/n): " BUCKET_EXISTS

    if [[ "$BUCKET_EXISTS" =~ ^[Yy]$ ]]; then
        while [ -z "$IMAGE_CREATION_BUCKET" ]; do
            read -p "Please enter the name of your existing bucket (without 'gs://'): " IMAGE_CREATION_BUCKET
            if [ -z "$IMAGE_CREATION_BUCKET" ]; then
                echo "Bucket name cannot be empty."
            fi
        done
    else
        # Prompt for a new bucket name with a default value
        DEFAULT_BUCKET_NAME="$SERVICE_NAME-bucket"
        read -p "Enter a name for the new GCS bucket [default: $DEFAULT_BUCKET_NAME]: " BUCKET_NAME_INPUT
        BUCKET_NAME_INPUT=${BUCKET_NAME_INPUT:-$DEFAULT_BUCKET_NAME}
        
        # GCS bucket names must be globally unique and follow certain rules.
        # We'll use the project ID to increase the chance of uniqueness.
        IMAGE_CREATION_BUCKET="${BUCKET_NAME_INPUT}-${PROJECT_ID}"

        echo "A new GCS bucket named '$IMAGE_CREATION_BUCKET' will be created in the '$REGION' region."
        read -p "Is this correct? (y/n): " CONFIRM_BUCKET_CREATION
        if [[ "$CONFIRM_BUCKET_CREATION" =~ ^[Yy]$ ]]; then
            echo "Creating GCS bucket..."
            if gcloud storage buckets create "gs://$IMAGE_CREATION_BUCKET" --project="$PROJECT_ID" --location="$REGION" --default-storage-class=STANDARD; then
                echo "Bucket '$IMAGE_CREATION_BUCKET' created successfully."
            else
                echo "Failed to create bucket. Please check permissions or try a different name."
                exit 1
            fi
        else
            echo "Bucket creation cancelled. Exiting."
            exit 1
        fi
    fi

    # --- Service Account Setup ---
    SA_NAME="sa-imagen-studio"
    SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    echo ""
    echo "--- Service Account Setup ---"
    echo "Checking for service account: $SA_EMAIL"

    # Check if the service account exists
    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        echo "Service account not found. Creating it now..."
        gcloud iam service-accounts create "$SA_NAME" \
            --description="Service account for Imagen Studio on Cloud Run" \
            --display-name="Imagen Studio SA" \
            --project="$PROJECT_ID"
        echo "Service account created."
    else
        echo "Service account already exists."
    fi

    # Grant required permissions
    echo "Granting required IAM roles to the service account..."

    # Grant Vertex AI User role
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/aiplatform.user" \
        --condition=None >/dev/null # Suppress verbose output

    # Grant Storage Admin role
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/storage.admin" \
        --condition=None >/dev/null # Suppress verbose output

    echo "IAM roles granted successfully."


    echo ""
    echo "--- Deployment Summary ---"
    echo "Project ID: $PROJECT_ID"
    echo "Service Name: $SERVICE_NAME"
    echo "Region: $REGION"
    echo "GCS Bucket: $IMAGE_CREATION_BUCKET"
    echo "Service Account: $SA_EMAIL"
    echo "--------------------------"
    echo ""

    read -p "Proceed with deployment? (y/n): " CONFIRM_DEPLOYMENT
    if [[ ! "$CONFIRM_DEPLOYMENT" =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
elif [[ "$DEPLOYMENT_TYPE" != "re-deploy" ]]; then
    echo "Invalid deployment type. Please enter 'fresh' or 're-deploy'."
    exit 1
fi

# --- Artifact Registry Setup ---
echo ""
echo "--- Artifact Registry Setup ---"
echo "Enabling Artifact Registry API..."
gcloud services enable artifactregistry.googleapis.com --project="$PROJECT_ID"

REPO_NAME="$SERVICE_NAME"
echo "Checking for Artifact Registry repository: $REPO_NAME"

if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo "Artifact Registry repository not found. Creating it now..."
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for $SERVICE_NAME" \
        --project="$PROJECT_ID"
    echo "Artifact Registry repository created."
else
    echo "Artifact Registry repository already exists."
fi


# --- Build and Deploy ---

IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

echo "Building the container image with Google Cloud Build..."
gcloud builds submit --tag "$IMAGE_PATH" .

echo "Deploying the container image to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_PATH" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "$SA_EMAIL" \
  --update-env-vars="IMAGE_CREATION_BUCKET=$IMAGE_CREATION_BUCKET,PROJECT_ID=$PROJECT_ID" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600

echo "Deployment complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format "value(status.url)")
echo "Your service is available at: $SERVICE_URL"
