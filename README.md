# Techno-Economic Assessment of WAPS Retrofits on Tankers

This project estimates the engine thrust needed to maintain a prescribed tanker speed under different wind conditions and sail configurations, then uses those thrust results in an Excel workbook to compare the life-cycle costs of a conventional tanker and a vessel retrofitted with a Wind-Assisted Propulsion System (WAPS).

The physical model is a simplified, quasi-steady engineering model for preliminary case studies. Its outputs should be treated as estimates, not as a validated ship-performance prediction.

## Repository contents

- `waps_thrust_model.py` — Python model that solves the lateral/yaw equilibrium for a wind-condition grid, calculates engine thrust, and exports labelled results.
- `requirements.txt` — Python package requirements.
- `Vessel_Costs_v15_09.xlsx` — Excel techno-economic model. It contains one engine-only baseline and eight WAPS case configurations; import the Python thrust results into the designated input area.
- `Vessels_WAPS_report_15_09_26.pdf` — report describing the modelling assumptions, equations, representative input data, and cost-estimation method.
- `outputs/` — created when the Python script runs; contains the thrust CSV and plot.

## Despription

### 1. Python thrust model

For a selected vessel and sail configuration, the Python script:

1. Defines vessel, hydrodynamic, aerodynamic and sail-array parameters.
2. Calculates apparent wind from the prescribed vessel surge speed and each true-wind condition.
3. Calculates the lift/drag-based forces and yaw moment of the sail array. The available sail technology flags are `1` for soft sail, `2` for rotor sail and `3` for suction sail.
4. Solves the steady sway-force and yaw-moment balance for sway velocity and rudder angle, while prescribing surge speed and assuming zero yaw rate.
5. Estimates the raw required engine thrust from


   $T_{e,raw}=D_u u_d^2-F_{x,WAPS}$,


   where $D_u u_d^2$ is the simplified hull-resistance estimate and $F_{x,WAPS}$ is the total longitudinal sail force.
6. Applies a non-negative floor for the thrust used by the costing model:

   
   $T_{e,used}=\max(0,T_{e,raw})$.


   The CSV retains both values. A negative raw value means the model predicts that the sails provide more longitudinal force than the estimated resistance at the prescribed speed.

### 2. Excel cost model

The thrust results derived from the Python script are processed in `Vessel_Costs_v15_09.xlsx`. The workbook combines the thrust grid and wind-condition probabilities with the vessel and WAPS cost inputs to estimate fuel consumption and annual cost components, including fuel, emissions compliance, electrical operating cost, maintenance/OPEX, installation costs and CAPEX. Its cost curves compare the engine-only baseline with the different WAPS configurations over a selected analysis horizon of up to 25 years.

The workflow is therefore:

**Vessel and WAPS inputs → Python wind/thrust sweep → CSV thrust results → Excel fuel and cost calculation → comparison of annual and life-cycle costs.**

## Requirements

Python 3.10 or later is recommended. The script uses NumPy, SciPy, and Matplotlib.

Install dependencies in a virtual environment from the repository root:

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the model

From the repository root, run:

```bash
python waps_thrust_model.py
```

By default, the script evaluates **13 wind speeds** (`0, 2, ..., 24 m/s`) and **10 wind angles** (`0°, 20°, ..., 180°`), giving 130 wind-condition cases. It prints the thrust summary to the terminal and creates:

- `outputs/thrust_results.csv` — one row per wind condition, including wind speed/angle, solver status, apparent wind, sail forces, raw thrust, and non-negative thrust used for costing.
- `outputs/thrust_surface.png` — a 3D plot of the calculated engine-thrust grid.


## Configure a vessel/sail case

Edit the case-specific input section in `main()` in `waps_thrust_model.py` before running:

- `u_d` — prescribed surge speed in m/s.
- `params.Du` in `YachtParameters` — surge-resistance coefficient in kg/m. The model assumes \(R_T(u)=D_u u^2\); calibrate `Du` from the selected vessel's resistance data and the matching reference speed.
- `sail_technology` — `1` soft sail, `2` rotor sail, or `3` suction sail.
- `defined_sail_area` — area assigned to each sail in m².
- `x_positions`, `y_positions` — sail positions in vessel/body coordinates. The script creates one sail for every x/y position combination; for example, three x-positions and two y-positions create six sails.
- `delta_s`, `lambda1`, `R_s`, `ks`, `sigma` — model inputs used by the selected technology.
- `wind_speeds`, `wind_angles_deg` — wind grid. These may be replaced by lists for a smaller diagnostic run.

Run the Python script separately for each vessel/WAPS configuration, keeping a clear record of the input settings alongside the generated CSV. The script overwrites the two output files on each run. Copy or rename them after each case if you need to retain all case results.

## Transfer the thrust results to Excel

1. Open `outputs/thrust_results.csv` and confirm that the intended wind cases completed successfully.
2. Use the `engine_thrust_used_N` column as the non-negative thrust series for the Excel costing model. Keep `engine_thrust_raw_N` for diagnostics.
3. Transfer the results into the designated thrust-input area of `Vessel_Costs_v15_09.xlsx`, matching rows by both `wind_speed_m_s` and `beta_w_body_deg_toward`. The Python output order is wind speed from low to high, and within each speed, wind angle from low to high.  The workbook uses the same order, so just paste the column directly.
4. Confirm that the workbook's wind probabilities and thrust rows correspond to the same wind grid before using its annual fuel and cost estimates.
5. Save a separate copy of the workbook for each alternative configuration, or clearly label which case each set of thrust values represents.


## Reproducibility and interpretation

Save the parameters used for every case together with its CSV output. Do not compare cases unless the vessel speed, wind grid/probabilities, engine assumptions and economic assumptions are aligned. The spreadsheet's results are conditional on the input data and modelling simplifications and should not be interpreted as a guarantee of actual fuel savings or commercial profitability.
