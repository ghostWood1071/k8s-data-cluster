from pod_command_patch import patch_pod


def pod_mutation_hook(pod):
    return patch_pod(pod)
