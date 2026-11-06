# Debugging notes: orders-api crash loop

Tags: #debugging #kubernetes

Pasted straight from the terminal, mostly unformatted.

## Pod events

Warning  BackOff  3m (x142 over 33m)  kubelet  Back-off restarting failed container orders-api in pod orders-api-7d9f8b6c5-x2k4q_prod
Normal   Pulled   2m                  kubelet  Container image "registry.example.com/orders-api:2.41" already present on machine
Warning  Failed   2m                  kubelet  Error: failed to create containerd task: OCI runtime create failed

## Stack trace (not fenced)

    java.lang.IllegalStateException: Pool exhausted
        at com.example.orders.db.Pool.acquire(Pool.java:88)
        at com.example.orders.web.CheckoutController.submit(CheckoutController.java:41)
        at jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
    Caused by: java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms.

## Application log

```text
2025-06-02T09:11:03.114Z INFO  orders  request id=a1 path=/checkout status=200 ms=412
2025-06-02T09:11:03.512Z WARN  orders  pool wait id=a2 waited_ms=2210 active=5 idle=0 pending=31
2025-06-02T09:11:04.001Z ERROR orders  request id=a3 path=/checkout status=500 ms=30001 err="Pool exhausted"
2025-06-02T09:11:04.350Z WARN  orders  pool wait id=a4 waited_ms=2890 active=5 idle=0 pending=44
2025-06-02T09:11:05.002Z ERROR orders  request id=a5 path=/checkout status=500 ms=30002 err="Pool exhausted"
2025-06-02T09:11:05.771Z WARN  orders  pool wait id=a6 waited_ms=3011 active=5 idle=0 pending=52
2025-06-02T09:11:06.120Z ERROR orders  request id=a7 path=/checkout status=500 ms=30000 err="Pool exhausted"
2025-06-02T09:11:06.912Z WARN  orders  pool wait id=a8 waited_ms=3320 active=5 idle=0 pending=61
2025-06-02T09:11:07.431Z ERROR orders  request id=a9 path=/checkout status=500 ms=30003 err="Pool exhausted"
2025-06-02T09:11:08.002Z WARN  orders  pool wait id=a10 waited_ms=3555 active=5 idle=0 pending=70
2025-06-02T09:11:08.644Z ERROR orders  request id=a11 path=/checkout status=500 ms=30001 err="Pool exhausted"
2025-06-02T09:11:09.210Z WARN  orders  pool wait id=a12 waited_ms=3801 active=5 idle=0 pending=77
2025-06-02T09:11:09.834Z ERROR orders  request id=a13 path=/checkout status=500 ms=30002 err="Pool exhausted"
2025-06-02T09:11:10.411Z WARN  orders  pool wait id=a14 waited_ms=4120 active=5 idle=0 pending=85
2025-06-02T09:11:11.002Z ERROR orders  request id=a15 path=/checkout status=500 ms=30000 err="Pool exhausted"
2025-06-02T09:11:11.633Z WARN  orders  pool wait id=a16 waited_ms=4390 active=5 idle=0 pending=93
2025-06-02T09:11:12.120Z ERROR orders  request id=a17 path=/checkout status=500 ms=30001 err="Pool exhausted"
2025-06-02T09:11:12.870Z WARN  orders  pool wait id=a18 waited_ms=4655 active=5 idle=0 pending=99
2025-06-02T09:11:13.402Z ERROR orders  request id=a19 path=/checkout status=500 ms=30002 err="Pool exhausted"
2025-06-02T09:11:14.011Z WARN  orders  pool wait id=a20 waited_ms=4902 active=5 idle=0 pending=108
2025-06-02T09:11:14.620Z ERROR orders  request id=a21 path=/checkout status=500 ms=30000 err="Pool exhausted"
2025-06-02T09:11:15.240Z WARN  orders  pool wait id=a22 waited_ms=5120 active=5 idle=0 pending=117
```

## A secret-looking token that is only an example

Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJleGFtcGxlIiwibmFtZSI6IkV4YW1wbGUgVXNlciIsImlhdCI6MTUxNjIzOTAyMn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5cSflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5cSflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5cSflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5cSflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

## Conclusion

The pool size was `5`. It should be `30`.
