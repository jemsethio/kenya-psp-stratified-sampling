.PHONY: test privacy

test:
	python -m unittest discover -s tests -v

privacy:
	python scripts/check_public_release.py

# Real run example: make run INPUT=/secure/source.xlsx WORKDIR=/secure/private_psp
run:
	PYTHONPATH=src python -m psp_sampling.run_pipeline --input "$(INPUT)" --workdir "$(WORKDIR)"

# Report example: make report PUBLIC_RESULTS=/secure/private_psp/public_aggregate_results OUT=/secure/report.docx
report:
	python scripts/build_academic_report.py --public-results "$(PUBLIC_RESULTS)" --output "$(OUT)"
