import google.auth
from google.cloud import storage
from googleapiclient.discovery import build
from flask import jsonify

def label_resources_in_project(request):
    try:
        # Set up Google Cloud credentials
        credentials, project = google.auth.default()

        # Initialize clients for Cloud Storage, Compute Engine, and GKE
        storage_client = storage.Client(credentials=credentials, project=project)
        compute_client = build('compute', 'v1', credentials=credentials)
        gke_client = build('container', 'v1', credentials=credentials)

        # Define the labels you want to apply
        labels_to_apply = {
            'environment': 'prod',
            'owner': 'jhante_charles',  # Replace "." with "_"
        }

        # --- Tagging Cloud Storage Buckets ---
        print("Tagging Cloud Storage Buckets...")
        buckets = storage_client.list_buckets()
        for bucket in buckets:
            bucket_labels = bucket.labels
            bucket_labels.update(labels_to_apply)
            bucket.labels = bucket_labels
            bucket.patch()
        
        # --- Tagging GCE Instances ---
        print("Tagging GCE Instances...")
        zones_request = compute_client.zones().list(project=project)
        zones_response = zones_request.execute()
        
        if 'items' in zones_response:
            for zone in zones_response['items']:
                zone_name = zone['name']
                instances_request = compute_client.instances().list(project=project, zone=zone_name)
                instances_response = instances_request.execute()
                
                if 'items' in instances_response:
                    for instance in instances_response['items']:
                        instance_name = instance['name']
                        print(f"Attempting to tag GCE instance: {instance_name} in zone {zone_name}")
                        
                        # Ensure labelFingerprint exists before setting labels
                        if 'labelFingerprint' in instance:
                            instance_labels = instance.get('labels', {})
                            instance_labels.update(labels_to_apply)

                            compute_client.instances().setLabels(
                                project=project,
                                zone=zone_name,
                                instance=instance_name,
                                body={
                                    'labels': instance_labels,
                                    'labelFingerprint': instance['labelFingerprint']
                                }
                            ).execute()
                            print(f"Labels applied to GCE instance: {instance_name}")
                        else:
                            print(f"Skipping instance {instance_name}: 'labelFingerprint' not found")

        # --- Tagging GKE Clusters ---
        print("Tagging GKE Clusters...")
        clusters_request = gke_client.projects().locations().clusters().list(
            parent=f'projects/{project}/locations/-'
        )
        clusters_response = clusters_request.execute()
        if 'clusters' in clusters_response:
            for cluster in clusters_response['clusters']:
                cluster_name = cluster['name']
                print(f"Attempting to tag GKE cluster: {cluster_name}")
                
                # Get existing labels and apply new labels
                cluster_labels = cluster.get('resourceLabels', {})
                cluster_labels.update(labels_to_apply)
                
                gke_client.projects().locations().clusters().setResourceLabels(
                    name=f'projects/{project}/locations/{cluster["location"]}/clusters/{cluster_name}',
                    body={
                        'resourceLabels': cluster_labels,
                        'labelFingerprint': cluster['labelFingerprint']
                    }
                ).execute()
                print(f"Labels applied to GKE cluster: {cluster_name}")

        return jsonify({"status": "Cloud Storage buckets, GCE instances, and GKE clusters tagged successfully!"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
