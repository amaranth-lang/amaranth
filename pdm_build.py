from pdm.backend._vendor.packaging.version import Version


# This is done in a PDM build hook without specifying `dynamic = [..., "version"]` to put all
# of the static metadata into pyproject.toml. Tools other than PDM will not execute this script
# and will use the generic version of the documentation URL (which redirects to /latest).
def pdm_build_initialize(context):
    version = Version(context.config.metadata["version"])
    if version.is_prerelease:
        url_version = "latest"
    else:
        url_version = f"v{version}"
    context.config.metadata["urls"]["Documentation"] += url_version
