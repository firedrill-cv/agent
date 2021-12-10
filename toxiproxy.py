import subprocess


def start_proxy_server():
    subprocess.Popen(
        ["toxiproxy-server"],
    )

    # create = subprocess.run(
    #     ["toxiproxy-cli",
    #      "create",
    #      "proxy",
    #      "chaos-proxy",
    #      "-l",
    #      "localhost:6666",
    #      "-u",
    #      "localhost:8888",
    #      ],
    #     stdin=subprocess.PIPE, stdout=subprocess.PIPE,  stderr=subprocess.STDOUT
    # )

    # result = subprocess.run(
    #     ["toxiproxy-cli",
    #      "list",
    #      "proxies"]
    # )

    # print(result.stdout)

    return
