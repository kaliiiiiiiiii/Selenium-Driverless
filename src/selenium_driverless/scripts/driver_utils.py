import typing


async def get_targets(target=None, driver=None, _type: str = None, context_id: str = None):
    if not (target or driver):
        raise ValueError("either base_target or driver need to be specified")
    from selenium_driverless.types.target import Target, TargetInfo
    target: Target
    res = await target.execute_cdp_cmd("Target.getTargets")
    _infos = res["targetInfos"]
    infos: typing.Dict[str, TargetInfo] = {}
    for info in _infos:
        _id = info["targetId"]

        async def getter():
            return await get_target(_id, base_target=target, driver=driver)

        info = await TargetInfo(info, getter)
        if ((not _type) or info.type == _type) and ((not context_id) or context_id == info.browser_context_id):
            infos[_id] = info
    return infos


# noinspection PyProtectedMember
async def get_target(target_id: str, base_target=None, driver=None, timeout: float = 2):
    if not (base_target or driver):
        raise ValueError("either base_target or driver need to be specified")

    from selenium_driverless.types.target import Target
    from selenium_driverless.webdriver import Chrome
    # noinspection PyTypeChecker
    target: Target = None
    if not base_target:
        base_target = driver
    context = None
    if driver:
        if isinstance(driver, Chrome):
            context = driver.current_context
        else:
            context = driver
        if context:
            target: Target = context._targets.get(target_id)
    if not target:
        if base_target and base_target._loop:
            from selenium_driverless.sync.target import Target as SyncTarget
            target: Target = await SyncTarget(host=base_target._host, target_id=target_id,
                                              is_remote=base_target._is_remote, loop=base_target._loop,
                                              timeout=timeout)
        else:
            target: Target = await Target(host=base_target._host, target_id=target_id,
                                          is_remote=base_target._is_remote, loop=base_target._loop, timeout=timeout)
        if context:
            context._targets[target_id] = target

            # noinspection PyUnusedLocal,PyProtectedMember
            def remove_target(code: str, reason: str):
                if target_id in driver._targets:
                    del context._targets[target_id]

            target.socket.on_closed.append(remove_target)
    return target


async def get_cookies(target) -> typing.List[dict]:
    """Returns a set of dictionaries, corresponding to cookies visible in
    the current session.

    :Usage:
        ::

            target.get_cookies()
    """
    cookies = await target.execute_cdp_cmd("Page.getCookies")
    return cookies["cookies"]


async def get_cookie(target, name) -> typing.Optional[typing.Dict]:
    """Get a single cookie by name. Returns the cookie if found, None if
    not.

    :Usage:
        ::

            target.get_cookie('my_cookie')
    """
    for cookie in await get_cookies(target):
        if cookie["name"] == name:
            return cookie


async def delete_cookie(target, name: str, url: str = None, domain: str = None, path: str = None) -> None:
    """Deletes a single cookie with the given name.

    :Usage:
        ::

            target.delete_cookie('my_cookie')
    """
    args = {"name": name}
    if url:
        args["url"] = url
    if domain:
        args["domain"] = domain
    if path:
        args["path"] = path
    await target.execute_cdp_cmd("Network.deleteCookies", args)


async def delete_all_cookies(target) -> None:
    """Delete all cookies in the scope of the session.

    :Usage:
        ::

            target.delete_all_cookies()
    """
    await target.execute_cdp_cmd("Network.clearBrowserCookies")


# noinspection GrazieInspection
async def add_cookie(target, cookie_dict, context_id: str = None) -> None:
    """Adds a cookie to your current session.

    :Args:
     - cookie_dict: A dictionary object, with required keys - "name" and "value";
        optional keys - "path", "domain", "secure", "httpOnly", "expiry", "sameSite"

    :Usage:
        ::

            target.add_cookie({'name' : 'foo', 'value' : 'bar'})
            target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/'})
            target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/', 'secure' : True})
            target.add_cookie({'name' : 'foo', 'value' : 'bar', 'sameSite' : 'Strict'})
    """
    if "sameSite" in cookie_dict:
        assert cookie_dict["sameSite"] in ["Strict", "Lax", "None"]
    args = {"cookies": [cookie_dict]}
    if context_id:
        args["Storage.setCookies"] = context_id
    await target.execute_cdp_cmd("Storage.setCookies", args)
