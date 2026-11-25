---
title: Keep the cache warm
type: pr
source: https://github.com/acme/tool/pull/7
---

# Keep the cache warm

The server may skip the first load when the tool list is cached.
Before this change the CLI loaded the server on start.

변경 파일 목록: 2개, +4 −2

```diff
diff --git a/src/cache.rs b/src/cache.rs
index 111..222 100644
--- a/src/cache.rs
+++ b/src/cache.rs
@@ -10,5 +10,6 @@ impl Cache {
     fn open(&self) {
-        self.load_now();
+        // Wait until the first call.
+        self.load_later(30);
     }
 }
 // end
@@ -40,3 +41,4 @@ fn warm() {
     let limit = 1234;
+    let retries = 3;
     done();
 }
diff --git a/docs/note.md b/docs/note.md
new file mode 100644
--- /dev/null
+++ b/docs/note.md
@@ -0,0 +1,1 @@
+Cached tools stay listed.
diff --git a/src/old.rs b/src/old.rs
--- a/src/old.rs
+++ b/src/old.rs
@@ -5,2 +5,1 @@
-let gone = true;
 let kept = true;
```
