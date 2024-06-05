# fake-docker

Replace Docker with K8s! Perfect for those brimming with self loathing!

## Dependencies

- NPM - `composerize`
- PIP - `Jinja2`

## Usage

Replace Docker on your path with `fake-docker.py`.
It will read the commands with composerize, then template them into a Job manifest for K8s, which it deploys with `kubectl`.

## Example

```
apiVersion: batch/v1
kind: Job
metadata:
  name: mock-cp-job 
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: mock-cp 
          command: 
            - /out/filein_harness
            - /work/tmp_blob
          image: ghcr.io/aixcc-sc/mock-cp:v3.0.2
          env:
            - name: LOCAL_USER
              value: 0:0
          volumeMounts:
            - mountPath: /work
              name: crs-scratch
              subPath: k8stest/mock-cp/work

            - mountPath: /src
              name: crs-scratch
              subPath: k8stest/mock-cp/src

            - mountPath: /out
              name: crs-scratch
              subPath: k8stest/mock-cp/out
         
      volumes:
         - name: crs-scratch 
           persistentVolumeClaim:
                claimName: crs-scratch
           name: crs-scratch
```

```
# ignored options for 'mock-cp'
# --cidfile=/crs_scratch/k8stest/mock-cp/out/output/1720727887.365000349--run_pov/docker.cid
name: <your project name>
services:
    mock-cp:
        volumes:
            - /crs_scratch/k8stest/mock-cp/work:/work
            - /crs_scratch/k8stest/mock-cp/src:/src
            - /crs_scratch/k8stest/mock-cp/out:/out
        env_file:
            - /crs_scratch/k8stest/mock-cp/.env.docker
        environment:
            - LOCAL_USER=0:0
        image: ghcr.io/aixcc-sc/mock-cp:v3.0.2
        command: '"cmd_harness.sh pov /work/tmp_blob filein_harness"'
```

```
docker run --cidfile "/crs_scratch/k8stest/mock-cp/out/output/1720727887.365000349--run_pov/docker.cid" -v /crs_scratch/k8stest/mock-cp/work:/work -v /crs_scratch/k8stest/mock-cp/src:/src -v /crs_scratch/k8stest/mock-cp/out:/out --env-file /crs_scratch/k8stest/mock-cp/.env.docker -e LOCAL_USER=0:0  ghcr.io/aixcc-sc/mock-cp:v3.0.2 "cmd_harness.sh pov /work/tmp_blob filein_harness"
```
