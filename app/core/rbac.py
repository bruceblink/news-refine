ROLE_PERMISSIONS = {
    "owner": {
        "org:manage",
        "user:invite",
        "event:read",
        "event:write",
    },
    "admin": {
        "user:invite",
        "event:read",
        "event:write",
    },
    "member": {
        "event:read",
    },
}