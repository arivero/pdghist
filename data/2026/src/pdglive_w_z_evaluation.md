# W and Z masses — PDG 2026, pdgLive (live evaluation)

The static `rpp2026-rev-w-mass.pdf` was frozen on **1 December 2025** with the
LHC-TeV MW Working Group 2023 combination as the world average. By
**2026-05-15** the PDG had already moved the live pdgLive `OUR EVALUATION` for
m_W to the next combination, which incorporates the new ATLAS 2024 refined and
CMS 2025 Run 2 measurements. The latest values live on the staging pdgLive at
`pdgprod.lbl.gov`, accessible through the same `DataBlock.action?node=…`
endpoint the public pdgLive uses.

- Source: pdgprod.lbl.gov staging pdgLive viewer for nodes S043M (W mass)
  and S044M (Z mass).
- Retrieved on 2026-05-15.
- The PDG database/SQLite for 2026 has not yet been published; pdgLive serves
  the in-progress evaluation directly from the staging environment.

## Headline values

| quantity | value (GeV) | uncertainty | label |
|---|---:|---:|---|
| m_W | **80.3625** | **±0.0077** | OUR EVALUATION (LHC-TeVatron MW Working Group) |
| m_Z | **91.1879** | **±0.0020** | OUR AVERAGE (LEP-1 + CDF) |

The m_W shifts down by 6.7 MeV and the uncertainty halves (13.3 → 7.7 MeV)
compared to the static review PDF — the new ATLAS/CMS LHC Run 2 measurements
finally got combined in. m_Z is essentially unchanged.

## Selected individual m_W inputs visible in the pdgLive viewer

These are the per-experiment numbers `DataBlock.action?node=S043M` lists
(with statistical and systematic errors shown separately):

```
80.3602 ± 0.0024 ± 0.0096   CMS Run 2 (2025)
80.3665 ± 0.0098 ± 0.0125   ATLAS Run 2 refined (2024)
80.354  ± 0.023  ± 0.022    LHCb
80.375  ± 0.011  ± 0.020    D0
80.4335 ± 0.0064 ± 0.0069   CDF II 2022 (excluded from the world average)
80.387  ± 0.012  ± 0.015    ATLAS Run 1 (2017)
80.370  ± 0.007  ± 0.017
80.367  ± 0.013  ± 0.022
80.401  ± 0.021  ± 0.038
80.413  ± 0.034  ± 0.034
```

## Selected individual m_Z inputs visible in the pdgLive viewer

```
91.1857 ± 0.0083 ± 0.0039
91.1923 ± 0.0071
91.1876 ± 0.0021     LEP-1 combination
91.084  ± 0.107
91.1872 ± 0.0033
91.1852 ± 0.0030
91.1863 ± 0.0028
91.1898 ± 0.0031
91.1875 ± 0.0039
91.1885 ± 0.0031
```
