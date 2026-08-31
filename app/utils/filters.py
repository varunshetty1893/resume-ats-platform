def register_filters(app):
    @app.template_filter("split_csv")
    def split_csv(value):
        """Turn a comma-separated string column into a clean list for loops."""
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    @app.template_filter("salary_range")
    def salary_range(job):
        if job.salary_min and job.salary_max:
            return f"₹{job.salary_min}–{job.salary_max} LPA"
        return "Not disclosed"
