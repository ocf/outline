from transpire import helm, surgery, utils
from transpire.resources import Deployment, Ingress, Secret, Service

name = "outline"
namespace = name
# A lil' bit of magic to get the adjacent versions.toml file. DWAI.
versions = utils.get_versions(__file__)
image = f"docker.io/outlinewiki/outline:{versions[name]['version']}"

# I had to use awscli to fix the CORS rules to make Outline work...
# aws --profile=ceph --endpoint=https://o3.ocf.io s3api get-bucket-cors --bucket ocf-outline
# {
#   "CORSRules": [
#     {
#       "AllowedHeaders": ["*"],
#       "AllowedMethods": ["PUT", "POST", "GET", "DELETE"],
#       "AllowedOrigins": ["https://docs.ocf.berkeley.edu"],
#       "MaxAgeSeconds": 3000
#     }
#   ]
# }


def objects():
    # Create an Ingress (a piece of standard configuration for web proxies).
    # This will configure the Envoy listening at 169.229.226.81 to forward
    # docs.ocf.berkeley.edu to the Service called "outline-web" on port 80.
    yield Ingress(
        host="docs.ocf.berkeley.edu",
        service_name=f"{name}-web",
        service_port=80,
    ).build()

    # This returns a Kubernetes secret object, which actually contains secret
    # data! Not to worry though, in production, transpire will intercept these
    # and deploy a VaultSecret. You can use this to generate default values
    # randomly, if possible. That makes your transpire module usable by others,
    # and slightly speeds up bootstrapping.
    yield Secret(
        name=name,
        # If you can automatically generate these, do so here.
        # Then you can just `transpire secret push` these to Vault!
        string_data={
            "OIDC_CLIENT_SECRET": "",
            "SECRET_KEY": "",
            "UTILS_SECRET": "",
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            # You have to specify the user/pass in the URL so this has to go in a secret.
            "DATABASE_URL": "",
            "REDIS_URL": "",
        },
    ).build()

    # Configuration details for outline-- notice how these are injected
    # as environment variables into the Deployment!
    yield {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name},
        "data": {
            "AWS_REGION": "rgw-hdd",
            "AWS_S3_ACL": "private",
            "AWS_S3_FORCE_PATH_STYLE": "true",
            "AWS_S3_UPLOAD_BUCKET_NAME": "ocf-outline",
            "AWS_S3_UPLOAD_BUCKET_URL": "https://o3.ocf.io",
            "AWS_S3_UPLOAD_MAX_SIZE": "26214400",
            "DEFAULT_LANGUAGE": "en_US",
            "ENABLE_UPDATES": "true",
            "FORCE_HTTPS": "true",
            "PGSSLMODE": "require",
            "PORT": "8080",
            "SLACK_MESSAGE_ACTIONS": "true",
            "URL": "https://docs.ocf.berkeley.edu",
            "OIDC_CLIENT_ID": "outline",
            "OIDC_AUTH_URI": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/auth",
            "OIDC_TOKEN_URI": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/token",
            "OIDC_USERINFO_URI": "https://idm.ocf.berkeley.edu/realms/ocf/protocol/openid-connect/userinfo",
            "OIDC_DISPLAY_NAME": "OCF",
        },
    }

    # This will create a container, and watch it if it dies to continually
    # restart it. Here we use a custom command, via the .patch() functionality.
    yield (
        Deployment(
            name=name,
            image=image,
            ports=[8080],
        )
        .with_configmap_env(name)
        .with_secrets_env(name)
    ).patch(
        surgery.make_edit_manifest(
            {
                ("spec", "template", "spec", "containers", 0, "command"): [
                    "sh",
                    "-c",
                    "yarn db:migrate && yarn start",
                ]
            }
        )
    ).build()

    yield Service(
        name="outline-web",
        selector={Deployment.SELECTOR_LABEL: name},
        port_on_pod=8080,
        port_on_svc=80,
    ).build()

    # This deploys everything you need to run redis! That was easy.
    redis_chart = helm.build_chart_from_versions(
        name="redis",
        versions=versions,
        # <https://github.com/bitnami/charts/tree/main/bitnami/redis>
        values={
            "architecture": "standalone",
            # This will emit a VaultSecret in production!
            "auth": {"password": ""},
        },
    )

    yield from surgery.edit_manifests(
        {
            # Chop off the automatically generated checksum for the secret only.
            # The checksums exist to ensure that Redis is restarted when its
            # configuration changes. However, the Helm chart randomly generates
            # a new password each run, even though the real secret in Vault
            # isn't changing, so we ignore only the secret checksum.
            ("StatefulSet", "redis-master"): surgery.make_edit_manifest(
                {
                    (
                        "spec",
                        "template",
                        "metadata",
                        "annotations",
                        "checksum/secret",
                    ): None,
                }
            )
        },
        redis_chart,
    )
