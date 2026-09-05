# Delivery note — {{job_id}}

Delivered {{delivered_date}} to {{customer_name}}.

## Files

| File | Format | SHA-256 | Bytes |
|---|---|---|---:|
{{file_rows}}

## Geometry conventions

| | |
|---|---|
| Units | {{units_out}} |
| Coordinate origin | {{coordinate_origin}} |
| Axis convention | {{axis_convention}} |
| Contracted tolerance | {{tolerance_mm}} mm |
| **Measured max deviation** | **{{max_deviation_mm}} mm** |
| Measured RMS deviation | {{rms_deviation_mm}} mm |
| Measurement method | {{measurement_method}} |

## What was measured vs. inferred

Measured directly from scan data:
{{measured_list}}

**Reconstructed by inference** — assumed symmetry, occluded regions, worn or damaged
areas rebuilt to intent rather than captured. Review these before manufacturing:
{{inferred_list}}

## Known limitations

{{limitations_list}}

## Software

{{software_versions}}

Revision {{revision}} of {{revision_rounds_included}} included.
Raw scan data is retained for {{working_data_days}} days and is yours on request.
