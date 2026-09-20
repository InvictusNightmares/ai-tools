package service

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"testing"
)

func TestJSONLConcurrentWritersAndCooperatingRotation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "usage.jsonl")
	if err := (&JSONLFile{Path: path}).Append(map[string]int{"writer": 99, "sequence": 0}); err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			sink := &JSONLFile{Path: path}
			for j := 0; j < 30; j++ {
				if err := sink.Append(map[string]int{"writer": id, "sequence": j}); err != nil {
					t.Error(err)
				}
			}
		}(i)
	}
	// Rename under the same stable lock; an open writer finishes before the
	// rename, and the next writer opens the new pathname.
	lock, err := os.OpenFile(path+".lock", os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	if err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
		t.Fatal(err)
	}
	if _, err = os.Stat(path); err == nil {
		if err = os.Rename(path, path+".1"); err != nil {
			t.Fatal(err)
		}
	}
	_ = syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	_ = lock.Close()
	wg.Wait()
	count := 0
	seen := map[[2]int]bool{}
	for _, file := range []string{path, path + ".1"} {
		f, err := os.Open(file)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			t.Fatal(err)
		}
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			var value map[string]int
			if err = json.Unmarshal(scanner.Bytes(), &value); err != nil {
				t.Fatal(err)
			}
			key := [2]int{value["writer"], value["sequence"]}
			if seen[key] {
				t.Fatal("duplicate record")
			}
			seen[key] = true
			count++
		}
		if err = scanner.Err(); err != nil {
			t.Fatal(err)
		}
		info, _ := f.Stat()
		if info.Mode().Perm() != 0600 {
			t.Fatal("unsafe mode")
		}
		f.Close()
	}
	if count != 121 {
		t.Fatalf("lost records=%d", 121-count)
	}
}

func TestJSONLSymlinkDoesNotModifyTarget(t *testing.T) {
	root := t.TempDir()
	target := filepath.Join(root, "target")
	path := filepath.Join(root, "usage.jsonl")
	if err := os.WriteFile(target, []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, path); err != nil {
		t.Fatal(err)
	}
	if err := (&JSONLFile{Path: path}).Append(map[string]int{"n": 1}); err == nil {
		t.Fatal("symlink accepted")
	}
	content, _ := os.ReadFile(target)
	if string(content) != "original" {
		t.Fatal("target modified")
	}
}
