var makeAFailure = (function () {
    function onFailure() {
        throw new Error('failed!')
    }

    // A bunch of functions that call each other until the stack is big enough
    // (the names are set just to look pretty, all functions do the same thing)
    function getUser(level) {
        if (level === 0) {
            getUser(level + 1)
        }
        if (level === 1) {
            getUser(level + 1)
        }
        if (level === 2) {
            getUser(level + 1)
        }
        if (level === 3) {
            getUser(level + 1)
        }
        if (level === 4) {
            getUser(level + 1)
        }
        if (level === 5) {
            getUser(level + 1)
        } else {
            createUser(0)
        }
    }

    function createUser(level) {
        if (level === 0) {
            createUser(level + 1)
        }
        if (level === 1) {
            createUser(level + 1)
        }
        if (level === 2) {
            createUser(level + 1)
        }
        if (level === 3) {
            createUser(level + 1)
        }
        if (level === 4) {
            createUser(level + 1)
        }
        if (level === 5) {
            createUser(level + 1)
        } else {
            setUser(0)
        }
    }

    function setUser(level) {
        if (level === 0) {
            setUser(level + 1)
        }
        if (level === 1) {
            setUser(level + 1)
        }
        if (level === 2) {
            setUser(level + 1)
        }
        if (level === 3) {
            setUser(level + 1)
        }
        if (level === 4) {
            setUser(level + 1)
        }
        if (level === 5) {
            setUser(level + 1)
        } else {
            addUser(0)
        }
    }

    function addUser(level) {
        if (level === 0) {
            addUser(level + 1)
        }
        if (level === 1) {
            addUser(level + 1)
        }
        if (level === 2) {
            addUser(level + 1)
        }
        if (level === 3) {
            addUser(level + 1)
        }
        if (level === 4) {
            addUser(level + 1)
        }
        if (level === 5) {
            addUser(level + 1)
        } else {
            deleteUser(0)
        }
    }

    function deleteUser(level) {
        if (level === 0) {
            deleteUser(level + 1)
        }
        if (level === 1) {
            deleteUser(level + 1)
        }
        if (level === 2) {
            deleteUser(level + 1)
        }
        if (level === 3) {
            deleteUser(level + 1)
        }
        if (level === 4) {
            deleteUser(level + 1)
        }
        if (level === 5) {
            deleteUser(level + 1)
        } else {
            banUser(0)
        }
    }

    function banUser(level) {
        if (level === 0) {
            banUser(level + 1)
        }
        if (level === 1) {
            banUser(level + 1)
        }
        if (level === 2) {
            banUser(level + 1)
        }
        if (level === 3) {
            banUser(level + 1)
        }
        if (level === 4) {
            banUser(level + 1)
        }
        if (level === 5) {
            banUser(level + 1)
        } else {
            updateUser(0)
        }
    }

    function updateUser(level) {
        if (level === 0) {
            updateUser(level + 1)
        }
        if (level === 1) {
            updateUser(level + 1)
        }
        if (level === 2) {
            updateUser(level + 1)
        }
        if (level === 3) {
            updateUser(level + 1)
        }
        if (level === 4) {
            updateUser(level + 1)
        }
        if (level === 5) {
            updateUser(level + 1)
        } else {
            displayUser(0)
        }
    }

    function displayUser(level) {
        if (level === 0) {
            displayUser(level + 1)
        }
        if (level === 1) {
            displayUser(level + 1)
        }
        if (level === 2) {
            displayUser(level + 1)
        }
        if (level === 3) {
            displayUser(level + 1)
        }
        if (level === 4) {
            displayUser(level + 1)
        }
        if (level === 5) {
            displayUser(level + 1)
        } else {
            login(0)
        }
    }

    function login(level) {
        if (level === 0) {
            login(level + 1)
        }
        if (level === 1) {
            login(level + 1)
        }
        if (level === 2) {
            login(level + 1)
        }
        if (level === 3) {
            login(level + 1)
        }
        if (level === 4) {
            login(level + 1)
        }
        if (level === 5) {
            login(level + 1)
        } else {
            logout(0)
        }
    }

    function logout(level) {
        if (level === 0) {
            logout(level + 1)
        }
        if (level === 1) {
            logout(level + 1)
        }
        if (level === 2) {
            logout(level + 1)
        }
        if (level === 3) {
            logout(level + 1)
        }
        if (level === 4) {
            logout(level + 1)
        }
        if (level === 5) {
            logout(level + 1)
        } else {
            getAccountDetails(0)
        }
    }

    function getAccountDetails(level) {
        if (level === 0) {
            getAccountDetails(level + 1)
        }
        if (level === 1) {
            getAccountDetails(level + 1)
        }
        if (level === 2) {
            getAccountDetails(level + 1)
        }
        if (level === 3) {
            getAccountDetails(level + 1)
        }
        if (level === 4) {
            getAccountDetails(level + 1)
        }
        if (level === 5) {
            getAccountDetails(level + 1)
        } else {
            getEvent(0)
        }
    }

    function getEvent(level) {
        if (level === 0) {
            getEvent(level + 1)
        }
        if (level === 1) {
            getEvent(level + 1)
        }
        if (level === 2) {
            getEvent(level + 1)
        }
        if (level === 3) {
            getEvent(level + 1)
        }
        if (level === 4) {
            getEvent(level + 1)
        }
        if (level === 5) {
            getEvent(level + 1)
        } else {
            logIssue(0)
        }
    }

    function logIssue(level) {
        if (level === 0) {
            logIssue(level + 1)
        }
        if (level === 1) {
            logIssue(level + 1)
        }
        if (level === 2) {
            logIssue(level + 1)
        }
        if (level === 3) {
            logIssue(level + 1)
        }
        if (level === 4) {
            logIssue(level + 1)
        }
        if (level === 5) {
            logIssue(level + 1)
        } else {
            getOptions(0)
        }
    }

    function getOptions(level) {
        if (level === 0) {
            getOptions(level + 1)
        }
        if (level === 1) {
            getOptions(level + 1)
        }
        if (level === 2) {
            getOptions(level + 1)
        }
        if (level === 3) {
            getOptions(level + 1)
        }
        if (level === 4) {
            getOptions(level + 1)
        }
        if (level === 5) {
            getOptions(level + 1)
        } else {
            setOptions(0)
        }
    }

    function setOptions(level) {
        if (level === 0) {
            setOptions(level + 1)
        }
        if (level === 1) {
            setOptions(level + 1)
        }
        if (level === 2) {
            setOptions(level + 1)
        }
        if (level === 3) {
            setOptions(level + 1)
        }
        if (level === 4) {
            setOptions(level + 1)
        }
        if (level === 5) {
            setOptions(level + 1)
        } else {
            onFailure()
        }
    }


    function test(maxStackLength) {
        getUser(0)
    }

    return test
})()
