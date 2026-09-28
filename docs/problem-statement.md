# Problem Statement

## Who is affected
- **Cyber cell investigators** (e.g. Jharkhand/Jamtara units) who receive fragmented evidence: bank statements, call detail records (CDRs), device/IMEI logs, complaint text, and accused names.
- **Victims**, whose money moves through several mule accounts within minutes.

## The real case
The Jamtara SIM-swap and vishing ring accounted for a large share of India's 95,000+ UPI fraud cases in FY2023. Investigators traced links between bank accounts, SIM cards and devices by hand, over weeks. Most cases went unsolved for lack of network visualization tools.

## Why existing solutions fall short
- Generic graph tools need clean, structured input; real evidence is unstructured, code-mixed (Hinglish/Devanagari) and inconsistent.
- Analytics tools show *that* a link exists, not *why we believe it* (provenance) or *what to do next*.
- Nothing translates findings into FIR-ready language, legal sections and time-critical freeze actions.

## Pain points
| Pain | Consequence |
|---|---|
| Manual link tracing across accounts, SIMs, devices | Weeks per case |
| Money is cashed out within minutes | Freeze window missed |
| Name variants (Rakesh / Rakesh Kumar / राकेश) | Same person treated as several |
| No hierarchy view (kingpin -> mule -> victim) | Mules arrested, kingpin untouched |
| Manual FIR drafting and evidence certification | Delays, weak charge sheets |

## Why now
UPI volume keeps growing, and SIM-swap plus mule-account fraud scales with it. Agentic AI (IBM Bob with tool access) can now turn messy text into a structured, explainable investigation in minutes.
