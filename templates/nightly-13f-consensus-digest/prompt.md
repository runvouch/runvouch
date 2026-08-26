You are a nightly research routine. Do exactly this, nothing else.

1. Read funds.txt in the current directory. Each non-comment line starts with a 13F filer CIK.
2. Call the DataSignals MCP tool hedge_fund_13f once, with filer_ciks set to that list of CIKs and max_results 50.
   The result contains one item with type "consensus" and a "picks" list (issuer, funds_holding, buyers, total_value, conviction).
3. Rank the picks by buyers, then funds_holding, then total_value. Keep the top 10.
4. If out/13f-digest.md exists, read it first and note its top 10 table.
5. Write out/13f-digest.md (overwrite) with:
   - a heading with today's date,
   - a table of the top 10: rank, issuer, funds buying, funds holding, total value, conviction,
   - a section "Changed since the previous digest": issuers that entered or left the top 10 and any change in buyers or holders.
     On the first run write "First run, nothing to compare against." If nothing changed write "No change."
   - one line stating that 13F is quarterly with a 45 day lag.
6. Do not call any other tool. Do not add opinions or recommendations. Plain ASCII.
