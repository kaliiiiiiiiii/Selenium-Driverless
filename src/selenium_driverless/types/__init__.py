class JSEvalException(Exception):
    def __init__(self, exception_details):
        super().__init__()
        self.exc_id = exception_details['exceptionId']
        self.text = exception_details["text"]
        self.line_n = exception_details['lineNumber']
        self.column_n = exception_details['columnNumber']
        exc = exception_details["exception"]
        self.type = exc["type"]
        self.subtype = exc["subtype"]
        self.class_name = exc["className"]
        self.description = exc["description"]
        self.obj_id = exc["objectId"]

    def __str__(self):
        return self.description
