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


class RemoteObject:
    # noinspection PyTypeChecker
    def __init__(self, target, js: str = None, obj_id: str = None, check_existence=True) -> None:
        from selenium_driverless.types.target import Target
        self._target: Target = target
        self._js = js
        self._check_exist = check_existence
        self._obj_id = obj_id
        self._started = False

    def __await__(self):
        return self.__aenter__().__await__()

    async def __aenter__(self):
        if not self._started:
            if self._check_exist:
                await self.obj_id
            self._started = True
        return self

    @property
    async def obj_id(self):
        if not self._obj_id:
            res = await self._target.execute_cdp_cmd("Runtime.evaluate",
                                                     {"expression": self._js,
                                                      "serializationOptions": {
                                                          "serialization": "idOnly"}})
            if "exceptionDetails" in res.keys():
                raise JSEvalException(res["exceptionDetails"])
            self._obj_id = res["result"]['objectId']
        return self._obj_id

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = 2, timeout: int = 2, execution_context_id: str = None, unique_context: bool = False):
        """
        example:
        script= "function(...arguments){this.click()}"
        "this" will be the element object
        """
        obj_id = await self.obj_id
        return await self._target.execute_raw_script(script, *args, await_res=await_res, serialization=serialization,
                                                     max_depth=max_depth, timeout=timeout, obj_id=obj_id,
                                                     execution_context_id=execution_context_id, unique_context=unique_context)

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None, timeout: int = 2,
                             only_value=True, execution_context_id: str = None, unique_context: bool = False):
        """
        exaple: script = "return this.click()"
        """
        obj_id = await self.obj_id
        return await self._target.execute_script(script, *args, serialization=serialization,
                                                 max_depth=max_depth, timeout=timeout, obj_id=obj_id,
                                                 only_value=only_value, execution_context_id=execution_context_id, unique_context=unique_context)

    async def execute_async_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                                   timeout: int = 2,
                                   only_value=True, execution_context_id: str = None, unique_context: bool = False):
        obj_id = await self.obj_id
        return await self._target.execute_async_script(script, *args, serialization=serialization,
                                                       max_depth=max_depth, timeout=timeout, obj_id=obj_id,
                                                       only_value=only_value,
                                                       execution_context_id=execution_context_id, unique_context=unique_context)

    async def get_props(self, own_properties_only=False,
                        accessor_props_only=False, non_indexed_props_only=False):
        args = {"objectId": await self.obj_id, "ownProperties": own_properties_only,
                "accessorPropertiesOnly": accessor_props_only,
                "nonIndexedPropertiesOnly": non_indexed_props_only}
        res = await self._target.execute_cdp_cmd("Runtime.getProperties", args)
        return res

    def __eq__(self, other):
        if isinstance(other, RemoteObject):
            if not (other._obj_id and self._obj_id):
                raise RuntimeError("RemoteObject isn't initialized, call RemoteObject._obj_id to initialize")
            return self._obj_id.split(".")[0] == other._obj_id.split(".")[0]
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)
