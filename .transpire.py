from transpire import helm

ingress = {
    "enabled": True,
    "ingressClassName": "cilium",
    "annotations": {
        "cert-manager.io/cluster-issuer": "letsencrypt",
        "ingress.kubernetes.io/force-ssl-redirect": "true",
        "kubernetes.io/tls-acme": "true",
    },
    "hosts": ["staffdocs.ocf.berkeley.edu"],
    "tls": [{"hosts": ["staffdocs.ocf.berkeley.edu"], "secretName": "outline-tls"}],
}

ceph_store = {
    "apiVersion": "ceph.rook.io/v1",
    "kind": "CephObjectStore",
    "metadata": {
        "name": "outline",
        "namespace": "outline",
    }
}

ceph_user = {
    "apiVersion": "ceph.rook.io/v1",
    "kind": "CephObjectStoreUser",
    "metadata": {
        "name": "outline",
        "namespace": "outline",
    },
    "spec": {
        "store": "outline",
        "displayName": "outline-user",
        "quotas": {
            "maxBuckets": "100",
            "maxSize": "10G",
            "maxObjects": "10000"
        },
        "capabilities": {
            "user": "*",
            "bucket": "*"
        }
    }
}

vault = {
    "apiVersion": "ricoberger.de/v1alpha1",
    "kind": "VaultSecret",
    "metadata": {"name": "outline-secret"},
    "spec": {
        "keys": ["OIDC_CLIENT_SECRET", "SECRET_KEY", "UTILS_SECRET"],
        "path": "kvv2/outline/outline",
        "type": "Opaque",
    },
}

postgres_vault = {
    "apiVersion": "ricoberger.de/v1alpha1",
    "kind": "VaultSecret",
    "metadata": {"name": "postgres-secret"},
    "spec": {
        "keys": ["OIDC_CLIENT_SECRET", "SECRET_KEY", "UTILS_SECRET"],
        "path": "kvv2/outline/postgres",
        "type": "Opaque",
    },
}

config = {
    "kind": "ConfigMap",
    "metadata": {"name": "outline", "namespace": "outline"},
    "apiVersion": "v1",
    "data": {
        "AWS_REGION": "default",
        "AWS_S3_ACL": "private",
        "AWS_S3_FORCE_PATH_STYLE": "true",
        "AWS_S3_UPLOAD_BUCKET_NAME": "outline",
        "AWS_S3_UPLOAD_BUCKET_URL": "http://localhost:9000",
        "AWS_S3_UPLOAD_MAX_SIZE": "26214400",
        "DEFAULT_LANGUAGE": "en_US",
        "ENABLE_UPDATES": "true",
        "FORCE_HTTPS": "true",
        "PGSSLMODE": "disable",
        "PORT": "80",
        "REDIS_URL": "redis://localhost:6379",
        "SLACK_MESSAGE_ACTIONS": "true",
        "URL": "https://staffdocs.ocf.berkeley.edu",
        "OIDC_CLIENT_ID": "outline",
        "OIDC_TOKEN_URI": "https://auth.ocf.berkeley.edu/auth/realms/ocf",
        "OIDC_DISPLAY_NAME": "Sign in with SSO"
    }
}

deploy = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {
        "name": "outline",
        "namespace": "outline"
    },
    "spec": {
        "selector": {
            "matchLabels": {"app": "outline"}
        },
        "strategy": {"type": "Recreate"},
        "template": {
            "metadata": {"labels": {"app": "outline"}},
            "spec": {
                "containers": [{
                    "command": ["sh", "-c", "yarn ", "sequelize:migrate ", "--env ", "production-ssl-disabled ", "&& yarn start"],
                    "envFrom": [
                        {"configMapRef": {"name": "outline"}},
                        {"secretRef": {"name": "outline-secret"}}
                    ],
                    "image": "outlinewiki/outline:latest",
                    "name": "outline",
                    "ports": [{"containerPort": 80}]}],

                "volumes": [{"name": "data",
                                "persistentVolumeClaim": {"claimName": "outline"}}]
            }
        }
    }
}                                       

redis = {
    "kind": "StatefulSet",
    "metadata": {"name": "outline-redis", "namespace": "outline"},
    "spec": {
        "selector": {"matchlabels": {"app": "outline"}},
        "serviceName": "postgres",
        "template": {
            "metadata": {"labels": {"app": "outline"}},
            "spec": {
                "containers": {
                    "image": "redis:latest",
                    "name": "redis",
                    "ports": [{"containerPort": 6379}]
                }
            }
        }
    }
}

postgres_config = {
    "kind": "ConfigMap",
    "metadata": {"name": "outline-postgres", "namespace": "outline"},
    "apiVersion": "v1",
    "data": {
        "POSTGRES_DB": "outline",
        "POSTGRES_USER": "outline"
    }
}


postgres = {
    "kind": "StatefulSet",
    "metadata": {"name": "outline-postgres", "namespace": "outline"},
    "spec": {
        "selector": {"matchlabels": {"app": "outline"}},
        "serviceName": "postgres",
        "template": {
            "metadata": {"labels": {"app": "outline"}},
            "spec": {
                "containers": {
                    "name": "postgres",
                    "image": "postgres:latest",
                    "ports": [{"containerPort": 5432}],
                    "volumeMounts": [{
                        "mountPath": "/var/lib/postgresql/data",
                        "name": "data",
                        "subPath": "postgres"}],
                    "envFrom": [{"configMapRef": {"name": "outline-postgres"}, "secretRef": "postgres-secret"}]
                }
            }
        }
    }
}

def objects():
    yield ingress
    yield ceph_store
    yield ceph_user
    yield vault
    yield postgres_vault
    yield redis
    yield postgres
    yield deploy
