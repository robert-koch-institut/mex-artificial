from dagster import (
    AssetSelection,
    Definitions,
    FilesystemIOManager,
    define_asset_job,
    load_assets_from_package_module,
)

from mex.extractors.pipeline import load_job_definitions

defs = Definitions(
    assets=[
        *(load_job_definitions().assets or ()),
        *load_assets_from_package_module(__import__("mex.artificial")),
    ],
    jobs=[
        define_asset_job(
            "merged_artificial",
            AssetSelection.groups("merged_artificial").upstream(),
        )
    ],
    resources={"io_manager": FilesystemIOManager()},
)
